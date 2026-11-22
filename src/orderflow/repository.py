"""Parameterized statements. The caller owns the transaction."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .models import Event, Order, OrderDetail, OrderError


def read_order(row) -> Order:
    fields = {key: row[key] for key in Order.__dataclass_fields__}
    fields["id"] = UUID(fields["id"])
    for key in ("created_at", "updated_at"):
        fields[key] = datetime.fromisoformat(fields[key])
    return Order(**fields)


def active_role(db: Connection, user_id: str) -> str | None:
    return db.execute(
        text("SELECT role FROM users WHERE id = :id AND active"),
        {"id": user_id},
    ).scalar_one_or_none()


def create(
    db: Connection,
    owner_id: str,
    service_id: str,
    quantity: int,
    note: str,
    *,
    occurred_at: datetime | None = None,
) -> Order:
    service_name = db.execute(
        text("SELECT name FROM service_catalogue WHERE id = :id AND active"),
        {"id": service_id},
    ).scalar_one_or_none()
    if service_name is None:
        raise OrderError("INVALID_INPUT", "Select an available catalogue service.")
    row = (
        db.execute(
            text("""
            INSERT INTO orders
                (id, owner_id, service_id, service_name_snapshot, quantity, note, created_at, updated_at)
            VALUES (:id, :owner, :service, :name, :quantity, :note, :now,
                    :now)
            RETURNING *
        """),
            {
                "id": str(uuid4()),
                "now": (occurred_at or datetime.now(UTC)).isoformat(timespec="microseconds"),
                "owner": owner_id,
                "service": service_id,
                "name": service_name,
                "quantity": quantity,
                "note": note,
            },
        )
        .mappings()
        .one()
    )
    return read_order(row)


def append_event(db: Connection, order: Order, previous: str | None, actor_id: str) -> None:
    db.execute(
        text("""
            INSERT INTO order_history (order_id, sequence, from_status, to_status, actor_id, occurred_at)
            VALUES (:id, :version, :previous, :status, :actor, :occurred)
        """),
        {
            "id": str(order.id),
            "version": order.version,
            "previous": previous,
            "status": order.status,
            "actor": actor_id,
            "occurred": order.updated_at.isoformat(timespec="microseconds"),
        },
    )


def not_found() -> OrderError:
    return OrderError("NOT_FOUND", "No accessible order was found.")


def list_visible(db: Connection, owner_id: str | None) -> list[Order]:
    scope = "" if owner_id is None else "WHERE o.owner_id = :owner"
    sql = f"SELECT o.* FROM orders o {scope} ORDER BY o.created_at DESC, o.id"
    rows = db.execute(text(sql), {"owner": owner_id}).mappings()
    return [read_order(row) for row in rows]


def ready_pickup_times(db: Connection) -> dict[UUID, datetime]:
    rows = db.execute(
        text("""
        SELECT o.id, h.occurred_at
        FROM orders o JOIN order_history h ON h.order_id = o.id AND h.sequence = o.version
        WHERE o.status = 'READY_FOR_PICKUP' AND h.to_status = 'READY_FOR_PICKUP'
    """)
    )
    return {UUID(row.id): datetime.fromisoformat(row.occurred_at) for row in rows}


def detail(db: Connection, order_id: UUID, owner_id: str | None) -> OrderDetail:
    scope = "" if owner_id is None else "AND o.owner_id = :owner"
    rows = (
        db.execute(
            text(f"""
            SELECT o.*, h.sequence, h.from_status, h.to_status, h.actor_id, h.occurred_at
            FROM orders o JOIN order_history h ON h.order_id = o.id
            WHERE o.id = :id {scope} ORDER BY h.sequence
        """),
            {"id": str(order_id), "owner": owner_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        raise not_found()
    order = read_order(rows[0])
    history = tuple(
        Event(
            row.sequence,
            row.from_status,
            row.to_status,
            row.actor_id,
            datetime.fromisoformat(row.occurred_at),
        )
        for row in rows
    )
    return OrderDetail(order, history)


def current_order(db: Connection, order_id: UUID, owner_id: str | None = None) -> Order:
    scope = "" if owner_id is None else " AND owner_id = :owner"
    row = (
        db.execute(
            text(f"SELECT * FROM orders WHERE id = :id{scope}"),
            {"id": str(order_id), "owner": owner_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise not_found()
    return read_order(row)


def advance(
    db: Connection,
    order_id: UUID,
    target: str,
    *,
    occurred_at: datetime | None = None,
) -> Order:
    row = (
        db.execute(
            text("""
            UPDATE orders SET status = :target, version = version + 1,
                updated_at = max(:now, updated_at)
            WHERE id = :id RETURNING *
        """),
            {
                "now": (occurred_at or datetime.now(UTC)).isoformat(timespec="microseconds"),
                "target": target,
                "id": str(order_id),
            },
        )
        .mappings()
        .one()
    )
    return read_order(row)


def available_services(db: Connection) -> dict[str, str]:
    rows = db.execute(text("SELECT id, name FROM service_catalogue WHERE active ORDER BY name"))
    return {row.id: row.name for row in rows}
