from datetime import UTC, datetime
from uuid import uuid4

import pytest

from orderflow.db import open_engine
from orderflow.models import Principal
from orderflow.services import OrderService
from support.import_review import import_snapshot


def test_verified_import_preserves_order_and_refuses_overwrite(tmp_path):
    order_id = uuid4()
    now = datetime.now(UTC).isoformat()
    snapshot = {
        "users": [{"id": "customer-a", "username": "alex", "role": "CUSTOMER", "active": True}],
        "service_catalogue": [{"id": "bw-print", "name": "Printing", "active": True}],
        "orders": [
            dict(
                id=str(order_id),
                owner_id="customer-a",
                service_id="bw-print",
                service_name_snapshot="Printing",
                quantity=2,
                note="Pickup",
                status="PENDING",
                version=0,
                created_at=now,
                updated_at=now,
            )
        ],
        "order_history": [
            dict(
                order_id=str(order_id),
                sequence=0,
                from_status=None,
                to_status="PENDING",
                actor_id="customer-a",
                occurred_at=now,
            )
        ],
    }
    target = tmp_path / "review.sqlite3"
    import_snapshot(snapshot, target)
    with pytest.raises(FileExistsError):
        import_snapshot(snapshot, target)
    engine = open_engine(target)
    try:
        detail = OrderService(engine).get_order(Principal("customer-a"), order_id)
        assert detail.order.note == "Pickup"
        assert detail.history[0].occurred_at == datetime.fromisoformat(now)
    finally:
        engine.dispose()
    failed = tmp_path / "invalid.sqlite3"
    snapshot["order_history"][0]["occurred_at"] = "invalid"
    with pytest.raises(ValueError):
        import_snapshot(snapshot, failed)
    assert not failed.exists()
