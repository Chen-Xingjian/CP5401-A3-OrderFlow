from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from orderflow.db import migrate
from orderflow.models import OrderError, Principal
from orderflow.services import OrderService

A = Principal("customer-a")
B = Principal("customer-b")
S = Principal("staff-s")
FLOW = ["PENDING", "CONFIRMED", "PROCESSING", "READY_FOR_PICKUP", "COMPLETED"]


@contextmanager
def rejected(code):
    with pytest.raises(OrderError) as error:
        yield
    assert error.value.code == code


def create(service, who=A):
    return service.create_order(who, service_id="bw-print", quantity=2)


def counts(engine):
    with engine.connect() as db:
        return tuple(
            db.exec_driver_sql(
                "SELECT (SELECT count(*) FROM orders), (SELECT count(*) FROM order_history)"
            ).one()
        )


def test_t01_t09_creation_and_history(service):
    order = create(service)
    assert isinstance(order.id, UUID)
    assert order.id != create(service).id
    assert (order.owner_id, order.service_id, order.service_name_snapshot) == (
        "customer-a",
        "bw-print",
        "Black and white printing",
    )
    assert (order.quantity, order.note, order.status, order.version) == (2, "", "PENDING", 0)
    detail = service.get_order(A, order.id)
    assert detail.order == order
    (event,) = detail.history
    assert (event.sequence, event.from_status, event.to_status, event.actor_id) == (
        0,
        None,
        "PENDING",
        "customer-a",
    )
    assert event.occurred_at == order.created_at == order.updated_at
    assert event.occurred_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize("quantity,note", [(1, ""), (99, "🌱" * 500)])
def test_t02_accept_boundaries_in_db(service, quantity, note):
    order = service.create_order(A, service_id="colour-print", quantity=quantity, note=note)
    stored = service.get_order(A, order.id)
    assert (stored.order.quantity, stored.order.note, len(stored.history)) == (quantity, note, 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", 0),
        ("quantity", 100),
        ("quantity", 1.5),
        ("quantity", True),
        ("note", "x" * 501),
        ("service_id", "binding"),
        ("service_id", "missing"),
        ("service_id", ""),
        ("service_id", None),
    ],
)
def test_t02_t03_rejection_leaves_both_tables_empty(service, database, field, value):
    payload = {"service_id": "bw-print", "quantity": 2, field: value}
    with rejected("INVALID_INPUT"):
        service.create_order(A, **payload)
    assert counts(database) == (0, 0)


def test_t03_snapshot_from_catalogue(service, database):
    first = create(service)
    with database.begin() as db:
        db.exec_driver_sql(
            "UPDATE service_catalogue SET name='Monochrome printing' WHERE id='bw-print'"
        )
    assert service.get_order(A, first.id).order.service_name_snapshot == "Black and white printing"
    assert create(service).service_name_snapshot == "Monochrome printing"


def test_t04_t12_trusted_identity_fields(service, database):
    for field, value in [
        ("owner_id", B.user_id),
        ("role", "STAFF"),
        ("service_name_snapshot", "Other"),
    ]:
        with pytest.raises(TypeError):
            service.create_order(A, service_id="bw-print", quantity=2, **{field: value})
    with rejected("FORBIDDEN"):
        create(service, S)
    assert counts(database) == (0, 0)
    order = create(service)
    original = service.get_order(A, order.id)
    for customer in [A, B]:
        with rejected("FORBIDDEN"):
            service.advance_order(customer, order.id, target="CONFIRMED", expected_version=0)
    assert service.get_order(A, order.id) == original


def test_t05_t06_t07_scoped_lists_details_and_histories(service):
    first, second = create(service, A), create(service, B)
    assert service.list_orders(A) == [first]
    assert service.list_orders(B) == [second]
    assert set(service.list_orders(S)) == {first, second}
    for owner, order in [(A, first), (B, second)]:
        assert service.get_order(S, order.id) == service.get_order(owner, order.id)
    errors = []
    for order_id in [first.id, uuid4()]:
        with pytest.raises(OrderError) as error:
            service.get_order(B, order_id)
        errors.append((error.value.code, str(error.value)))
    assert errors == [("NOT_FOUND", "No accessible order was found.")] * 2


@pytest.mark.parametrize(
    "actor", [None, Principal("unknown"), Principal("inactive"), Principal("")]
)
def test_t08_invalid_identity(service, database, actor):
    order = create(service)
    for operation in [
        lambda: create(service, actor),
        lambda: service.list_orders(actor),
        lambda: service.get_order(actor, order.id),
        lambda: service.advance_order(actor, order.id, target="CONFIRMED", expected_version=0),
    ]:
        with rejected("UNAUTHENTICATED"):
            operation()
    assert counts(database) == (1, 1)
    assert service.get_order(A, order.id).order == order


def test_t08_role_and_activation_rechecked_each_call(service, database):
    order = create(service)
    assert service.get_order(S, order.id).order == order
    with database.begin() as db:
        db.exec_driver_sql("UPDATE users SET active=false WHERE id='staff-s'")
    with rejected("UNAUTHENTICATED"):
        service.advance_order(S, order.id, target="CONFIRMED", expected_version=0)
    assert (counts(database), service.get_order(A, order.id).order) == ((1, 1), order)


def test_t10_full_lifecycle(service):
    order = create(service)
    for version, target in enumerate(FLOW[1:], start=1):
        updated = service.advance_order(S, order.id, target=target, expected_version=version - 1)
        detail = service.get_order(A, order.id)
        assert detail.order == updated
        assert (updated.status, updated.version) == (target, version)
        assert [e.sequence for e in detail.history] == list(range(version + 1))
        assert [e.from_status for e in detail.history] == [None, *FLOW[:version]]
        assert [e.to_status for e in detail.history] == FLOW[: version + 1]
        assert [e.actor_id for e in detail.history] == [A.user_id, *[S.user_id] * version]
        assert all(e.occurred_at.utcoffset() == timedelta(0) for e in detail.history)
        assert detail.history[-1].occurred_at == updated.updated_at
        print(f"{updated.status} | version={version} | history={len(detail.history)}")


@pytest.mark.parametrize(
    "stage,target",
    [
        (0, "PROCESSING"),
        (1, "COMPLETED"),
        (1, "PENDING"),
        (1, "CONFIRMED"),
        (1, "UNKNOWN"),
        (4, "CONFIRMED"),
    ],
)
def test_t11_t13_rejected_transitions_preserve_every_field(service, stage, target):
    order = create(service)
    for version in range(stage):
        service.advance_order(S, order.id, target=FLOW[version + 1], expected_version=version)
    before = service.get_order(A, order.id)
    with rejected("INVALID_TRANSITION"):
        service.advance_order(S, order.id, target=target, expected_version=stage)
    assert service.get_order(A, order.id) == before


def test_t14_replay_returns_refresh_before_edge_check(service):
    order = create(service)
    service.advance_order(S, order.id, target="CONFIRMED", expected_version=0)
    before = service.get_order(A, order.id)
    with pytest.raises(OrderError) as error:
        service.advance_order(S, order.id, target="CONFIRMED", expected_version=0)
    assert error.value.code == "STALE_VERSION"
    assert "refresh" in str(error.value).lower()
    assert service.get_order(A, order.id) == before


def test_t18_orders_stay_independent(service):
    a, b = create(service, A), create(service, B)
    before = service.get_order(B, b.id)
    service.advance_order(S, a.id, target="CONFIRMED", expected_version=0)
    service.advance_order(S, a.id, target="PROCESSING", expected_version=1)
    assert service.get_order(B, b.id) == before
    service.advance_order(Principal("staff-t"), b.id, target="CONFIRMED", expected_version=0)
    assert [e.actor_id for e in service.get_order(B, b.id).history] == ["customer-b", "staff-t"]
    assert [e.actor_id for e in service.get_order(A, a.id).history] == [
        "customer-a",
        "staff-s",
        "staff-s",
    ]


def test_t19_reopen_database_and_rerun_migration(service, database):
    order = create(service)
    service.advance_order(S, order.id, target="CONFIRMED", expected_version=0)
    expected = service.get_order(A, order.id)
    database.dispose()
    migrate(database)
    assert OrderService(database).get_order(A, order.id) == expected
    with database.connect() as db:
        assert db.exec_driver_sql("SELECT count(*) FROM schema_migrations").scalar_one() == 1


def test_invalid_reference_and_version_preserve_order(service):
    order = create(service)
    before = service.get_order(A, order.id)
    with rejected("INVALID_INPUT"):
        service.get_order(A, "invalid-id")
    with rejected("INVALID_INPUT"):
        service.advance_order(S, order.id, target="CONFIRMED", expected_version=True)
    with rejected("NOT_FOUND"):
        service.advance_order(S, uuid4(), target="CONFIRMED", expected_version=0)
    assert service.get_order(A, order.id) == before
