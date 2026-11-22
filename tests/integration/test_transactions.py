from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event

from orderflow.models import OrderError, Principal

A = Principal("customer-a")
S = Principal("staff-s")


def confirmed_order(service):
    order = service.create_order(A, service_id="bw-print", quantity=2)
    return service.advance_order(S, order.id, target="CONFIRMED", expected_version=0)


@pytest.mark.parametrize("operation", ["advance", "create"])
@pytest.mark.parametrize("stage", ["before_history_insert", "at_commit"])
def test_t15_t16_atomic_failure(service, database, operation, stage):
    order = confirmed_order(service)
    before = service.get_order(A, order.id)
    trigger = (
        "CREATE TRIGGER fail_write BEFORE INSERT ON order_history"
        if stage == "before_history_insert"
        else "CREATE CONSTRAINT TRIGGER fail_write AFTER INSERT ON order_history "
        "DEFERRABLE INITIALLY DEFERRED"
    )
    with database.begin() as db:
        # PostgreSQL sequence increments survive rollback and prove the fault was reached.
        db.exec_driver_sql("CREATE SEQUENCE fault_hits")
        db.exec_driver_sql("""
            CREATE FUNCTION fail_history() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM nextval('fault_hits');
                RAISE EXCEPTION 'Test-only storage interruption';
            END $$;
        """)
        db.exec_driver_sql(f"{trigger} FOR EACH ROW EXECUTE FUNCTION fail_history()")
    with pytest.raises(OrderError) as failure:
        if operation == "advance":
            service.advance_order(S, order.id, target="PROCESSING", expected_version=1)
        else:
            service.create_order(A, service_id="colour-print", quantity=3)
    assert failure.value.code == "PERSISTENCE_ERROR"
    assert "Test-only" not in str(failure.value)
    assert service.get_order(A, order.id) == before
    with database.connect() as db:
        observed = tuple(
            db.exec_driver_sql("""
            SELECT (SELECT count(*) FROM orders), (SELECT count(*) FROM order_history),
                   (SELECT is_called FROM fault_hits), (SELECT last_value FROM fault_hits)
        """).one()
        )
    assert observed == (1, 2, True, 1)
    print(
        f"{operation} / {stage} | error={failure.value.code} | "
        f"orders={observed[0]} | history={observed[1]} | state=CONFIRMED | version=1"
    )


def test_t17_two_connections_one_commit(service, database):
    order = confirmed_order(service)
    ready = Barrier(2, timeout=8)

    def rendezvous(db, cursor, statement, parameters, context, executemany):
        # Both real connections must reach the row lock before either can finish.
        if "FROM orders WHERE id" in statement and "FOR UPDATE" in statement:
            ready.wait()

    def worker(staff):
        seen = service.get_order(staff, order.id).order
        assert (seen.status, seen.version) == ("CONFIRMED", 1)
        try:
            service.advance_order(
                staff, order.id, target="PROCESSING", expected_version=seen.version
            )
        except OrderError as error:
            return staff.user_id, error.code
        return staff.user_id, "COMMITTED"

    event.listen(database, "before_cursor_execute", rendezvous)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, [S, Principal("staff-t")]))
    finally:
        event.remove(database, "before_cursor_execute", rendezvous)
    (winner,) = [actor for actor, result in results if result == "COMMITTED"]
    assert sorted(result for _, result in results) == ["COMMITTED", "STALE_VERSION"]
    final = service.get_order(A, order.id)
    assert (final.order.status, final.order.version, len(final.history)) == ("PROCESSING", 2, 3)
    assert [e.sequence for e in final.history] == [0, 1, 2]
    assert (
        final.history[-1].from_status,
        final.history[-1].to_status,
        final.history[-1].actor_id,
    ) == ("CONFIRMED", "PROCESSING", winner)
    print(
        f"Workers={dict(results)} | status={final.order.status} | version={final.order.version} "
        f"| history={len(final.history)}"
    )
