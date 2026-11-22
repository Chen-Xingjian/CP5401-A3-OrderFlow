import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from orderflow import db, demo
from orderflow.models import OrderError, Principal
from orderflow.services import OrderService

A = Principal("customer-a")
B = Principal("customer-b")
S = Principal("staff-s")
STAGES = ("PENDING", "CONFIRMED", "PROCESSING", "READY_FOR_PICKUP", "COMPLETED")


def at_stage(service, stage, owner=A):
    order = service.create_order(owner, service_id="bw-print", quantity=2, note="Counter pickup")
    for target in STAGES[1 : STAGES.index(stage) + 1]:
        order = service.advance_order(S, order.id, target=target, expected_version=order.version)
    return order


@pytest.mark.parametrize("stage", ["PENDING", "CONFIRMED"])
def test_t21_owner_cancels_before_production(database, service, stage):
    order = at_stage(service, stage)
    before = service.get_order(A, order.id)
    result = service.cancel_order(A, order.id, expected_version=order.version)
    database.dispose()
    after = service.get_order(A, order.id)
    assert after == service.get_order(S, order.id)
    assert after.order == result and result.status == "CANCELLED"
    assert result.version == order.version + 1
    assert after.history[:-1] == before.history
    event = after.history[-1]
    assert (event.sequence, event.from_status, event.to_status, event.actor_id) == (
        result.version,
        stage,
        "CANCELLED",
        "customer-a",
    )
    assert event.occurred_at == result.updated_at
    assert (result.note, result.quantity, result.owner_id, result.created_at) == (
        order.note,
        order.quantity,
        order.owner_id,
        order.created_at,
    )
    assert service.list_orders(A) == service.list_orders(S) == [result]


@pytest.mark.parametrize("stage", STAGES[2:])
def test_t22_cutoff(service, stage):
    order = at_stage(service, stage)
    before = service.get_order(A, order.id)
    with pytest.raises(OrderError) as error:
        service.cancel_order(A, order.id, expected_version=order.version)
    assert error.value.code == "INVALID_TRANSITION"
    assert service.get_order(A, order.id) == before


@pytest.mark.parametrize(
    "actor,code",
    [
        (B, "NOT_FOUND"),
        (S, "FORBIDDEN"),
        (Principal("staff-t"), "FORBIDDEN"),
        (None, "UNAUTHENTICATED"),
        (Principal("inactive"), "UNAUTHENTICATED"),
    ],
)
def test_t23_access_before_version(service, actor, code):
    order = at_stage(service, "CONFIRMED")
    before = service.get_order(A, order.id)
    messages = []
    for reference in [order.id, uuid4()]:
        with pytest.raises(OrderError) as error:
            service.cancel_order(actor, reference, expected_version=0)
        assert error.value.code == code
        messages.append(str(error.value))
    assert messages[0] == messages[1]
    assert service.get_order(A, order.id) == before


@pytest.mark.parametrize("reference,version", [("invalid", 0), (None, True), (None, -1)])
def test_cancel_invalid_inputs(service, reference, version):
    order = at_stage(service, "PENDING")
    before = service.get_order(A, order.id)
    with pytest.raises(OrderError) as error:
        service.cancel_order(A, reference or order.id, expected_version=version)
    assert error.value.code == "INVALID_INPUT"
    assert service.get_order(A, order.id) == before


def test_t24_terminal_and_retries(service):
    order = at_stage(service, "PENDING")
    service.cancel_order(A, order.id, expected_version=0)
    before = service.get_order(A, order.id)
    for version, code in [(0, "STALE_VERSION"), (1, "ALREADY_CANCELLED")]:
        with pytest.raises(OrderError) as error:
            service.cancel_order(A, order.id, expected_version=version)
        assert error.value.code == code
    for target in (*STAGES, "CANCELLED"):
        with pytest.raises(OrderError) as error:
            service.advance_order(S, order.id, target=target, expected_version=1)
        assert error.value.code == "INVALID_TRANSITION"
    assert service.get_order(A, order.id) == before


def test_t25_cancel_races_start_production(service):
    order = at_stage(service, "CONFIRMED")
    ready = Barrier(2, timeout=8)

    def worker(actor):
        version = service.get_order(actor, order.id).order.version
        ready.wait()
        try:
            if actor == A:
                result = service.cancel_order(A, order.id, expected_version=version)
            else:
                result = service.advance_order(
                    S, order.id, target="PROCESSING", expected_version=version
                )
        except OrderError as error:
            return error.code
        return result.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(worker, (A, S)))
    after = service.get_order(A, order.id)
    expected = {
        ("CANCELLED", "STALE_VERSION"): ("CANCELLED", "customer-a"),
        ("STALE_VERSION", "PROCESSING"): ("PROCESSING", "staff-s"),
    }
    status, actor = expected[results]
    assert (after.order.status, after.order.version, len(after.history)) == (status, 2, 3)
    event = after.history[-1]
    assert (event.from_status, event.to_status, event.actor_id, event.sequence) == (
        "CONFIRMED",
        status,
        actor,
        2,
    )


def test_t27_migrate_populated_v10_copy(tmp_path, monkeypatch):
    original_path = tmp_path / "baseline.sqlite3"
    copy_path = tmp_path / "candidate.sqlite3"
    old_migrations = tmp_path / "v10"
    old_migrations.mkdir()
    for name in ("001_baseline.sql", "002_account_passwords.sql"):
        (old_migrations / name).write_bytes((db.MIGRATIONS / name).read_bytes())
    original = db.open_engine(original_path)
    with monkeypatch.context() as patch:
        patch.setattr(db, "MIGRATIONS", old_migrations)
        demo.prepare(original)
    legacy = OrderService(original)
    confirmed = at_stage(legacy, "CONFIRMED")
    completed = at_stage(legacy, "COMPLETED", owner=B)
    snapshots = [legacy.get_order(S, o.id) for o in (confirmed, completed)]
    original.dispose()
    with sqlite3.connect(original_path) as source, sqlite3.connect(copy_path) as dest:
        source.backup(dest)
    upgraded = db.open_engine(copy_path)
    try:
        db.migrate(upgraded)
        db.migrate(upgraded)
        svc = OrderService(upgraded)
        assert [svc.get_order(S, o.id) for o in (confirmed, completed)] == snapshots
        with upgraded.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert "orders_owner_created_idx" in [
                r[1] for r in conn.exec_driver_sql("PRAGMA index_list(orders)")
            ]
        result = svc.advance_order(S, confirmed.id, target="PROCESSING", expected_version=1)
        assert result.status == "PROCESSING"
        assert svc.get_order(B, completed.id) == snapshots[1]
    finally:
        upgraded.dispose()
