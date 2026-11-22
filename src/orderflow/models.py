from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class OrderError(Exception):
    """Public error with a stable code and a message suitable for the caller."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Principal:
    """User ID supplied by a trusted server-side authentication adapter."""

    user_id: str


@dataclass(frozen=True)
class Order:
    id: UUID
    owner_id: str
    service_id: str
    service_name_snapshot: str
    quantity: int
    note: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Event:
    sequence: int
    from_status: str | None
    to_status: str
    actor_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class OrderDetail:
    order: Order
    history: tuple[Event, ...]
