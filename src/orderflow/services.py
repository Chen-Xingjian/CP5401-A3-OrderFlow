"""Order operations for authenticated customers and staff."""

from uuid import UUID

from sqlalchemy.engine import Connection, Engine

from . import repository, rules
from .db import transaction
from .models import Order, OrderDetail, OrderError, Principal


def _role(db: Connection, principal: Principal | None) -> str:
    if isinstance(principal, Principal) and isinstance(principal.user_id, str):
        try:
            rules.validate_text(principal.user_id, "the identity")
        except OrderError:
            pass
        else:
            role = repository.active_role(db, principal.user_id)
            if role is not None:
                return role
    raise OrderError("UNAUTHENTICATED", "Sign in with an active account.")


def _require_role(actual: str, required: str) -> None:
    if actual != required:
        raise OrderError("FORBIDDEN", "Your account cannot perform this operation.")


def _record_transition(db: Connection, current: Order, target: str, principal: Principal) -> Order:
    updated = repository.advance(db, current.id, target)
    repository.append_event(db, updated, current.status, principal.user_id)
    return updated


class OrderService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def account_role(self, principal: Principal) -> str:
        with transaction(self.engine) as db:
            return _role(db, principal)

    def available_services(self, principal: Principal) -> dict[str, str]:
        with transaction(self.engine) as db:
            _require_role(_role(db, principal), "CUSTOMER")
            return repository.available_services(db)

    def create_order(
        self, principal: Principal | None, *, service_id: str, quantity: int, note: str = ""
    ) -> Order:
        with transaction(self.engine, write=True) as db:
            role = _role(db, principal)
            rules.validate_creation(service_id, quantity, note)
            _require_role(role, "CUSTOMER")
            order = repository.create(db, principal.user_id, service_id, quantity, note)
            repository.append_event(db, order, None, principal.user_id)
            return order

    def list_orders(self, principal: Principal | None) -> list[Order]:
        with transaction(self.engine) as db:
            role = _role(db, principal)
            return repository.list_visible(db, principal.user_id if role == "CUSTOMER" else None)

    def get_order(self, principal: Principal | None, order_id: UUID) -> OrderDetail:
        with transaction(self.engine) as db:
            role = _role(db, principal)
            rules.validate_order_id(order_id)
            return repository.detail(
                db, order_id, principal.user_id if role == "CUSTOMER" else None
            )

    def advance_order(
        self, principal: Principal | None, order_id: UUID, *, target: str, expected_version: int
    ) -> Order:
        with transaction(self.engine, write=True) as db:
            role = _role(db, principal)
            rules.validate_order_id(order_id)
            rules.validate_update(target, expected_version)
            _require_role(role, "STAFF")
            current = repository.current_order(db, order_id)
            rules.check_version(current.version, expected_version)
            rules.check_transition(current.status, target)
            return _record_transition(db, current, target, principal)

    def cancel_order(
        self, principal: Principal | None, order_id: UUID, *, expected_version: int
    ) -> Order:
        with transaction(self.engine, write=True) as db:
            role = _role(db, principal)
            rules.validate_order_id(order_id)
            rules.validate_update("CANCELLED", expected_version)
            _require_role(role, "CUSTOMER")
            current = repository.current_order(db, order_id, owner_id=principal.user_id)
            rules.check_version(current.version, expected_version)
            rules.check_cancellation(current.status)
            return _record_transition(db, current, "CANCELLED", principal)
