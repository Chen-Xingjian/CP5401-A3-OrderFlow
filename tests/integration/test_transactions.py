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
    with database.begin() as db:
        if stage == "before_history_insert":
            db.exec_driver_sql("""
                CREATE TRIGGER fail_write BEFORE INSERT ON order_history
                BEGIN SELECT RAISE(ABORT, 'Test-only storage interruption'); END
            """)
        else:
            # The event insert succeeds; SQLite rejects the missing parent at commit.
            db.exec_driver_sql("""
                CREATE TABLE commit_fault (missing TEXT REFERENCES users(id)
                                          DEFERRABLE INITIALLY DEFERRED)
            """)
            db.exec_driver_sql("""
                CREATE TRIGGER fail_write AFTER INSERT ON order_history
                BEGIN INSERT INTO commit_fault VALUES ('missing-parent'); END
            """)
    inserted = []

    def after_statement(conn, cursor, sql, params, context, many):
        if "INSERT INTO order_history" in sql:
            inserted.append(True)

    event.listen(database, "after_cursor_execute", after_statement)
    with pytest.raises(OrderError) as failure:
        if operation == "advance":
            service.advance_order(S, order.id, target="PROCESSING", expected_version=1)
        else:
            service.create_order(A, service_id="colour-print", quantity=3)
    event.remove(database, "after_cursor_execute", after_statement)
    assert bool(inserted) == (stage == "at_commit")
    assert failure.value.code == "PERSISTENCE_ERROR"
    assert "Test-only" not in str(failure.value)
    assert service.get_order(A, order.id) == before
    with database.connect() as db:
        observed = tuple(
            db.exec_driver_sql("""
            SELECT (SELECT count(*) FROM orders), (SELECT count(*) FROM order_history)
        """).one()
        )
    assert observed == (1, 2)
    print(
        f"{operation} / {stage} | error={failure.value.code} | "
        f"orders={observed[0]} | history={observed[1]} | state=CONFIRMED | version=1"
    )


def test_t17_two_connections_one_commit(service, database):
    order = confirmed_order(service)
    ready = Barrier(2, timeout=8)

    def worker(staff):
        seen = service.get_order(staff, order.id).order
        assert (seen.status, seen.version) == ("CONFIRMED", 1)
        ready.wait()
        try:
            service.advance_order(
                staff, order.id, target="PROCESSING", expected_version=seen.version
            )
        except OrderError as error:
            return staff.user_id, error.code
        return staff.user_id, "COMMITTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [S, Principal("staff-t")]))
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
