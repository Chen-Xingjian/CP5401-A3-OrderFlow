from datetime import UTC, datetime, timedelta
from uuid import UUID

from .models import OrderError

CANCELLABLE = frozenset({"PENDING", "CONFIRMED"})

NEXT_STATUS = {
    "PENDING": "CONFIRMED",
    "CONFIRMED": "PROCESSING",
    "PROCESSING": "READY_FOR_PICKUP",
    "READY_FOR_PICKUP": "COMPLETED",
}


def pickup_is_overdue(ready_at: datetime, as_of: datetime) -> bool:
    return as_of.astimezone(UTC) - ready_at.astimezone(UTC) >= timedelta(hours=48)


def validate_text(value: object, label: str) -> None:
    if not isinstance(value, str) or "\x00" in value:
        raise OrderError("INVALID_INPUT", f"Enter valid text for {label}.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise OrderError("INVALID_INPUT", f"Enter valid text for {label}.") from None


def validate_creation(service_id: str, quantity: int, note: str) -> None:
    validate_text(service_id, "the service")
    if not service_id.strip():
        raise OrderError("INVALID_INPUT", "Select a catalogue service.")
    if type(quantity) is not int or not 1 <= quantity <= 99:
        raise OrderError("INVALID_INPUT", "Enter a whole quantity from 1 to 99.")
    validate_text(note, "the note")
    if len(note) > 500:
        raise OrderError("INVALID_INPUT", "Use at most 500 characters for the note.")


def validate_order_id(order_id: UUID) -> None:
    if not isinstance(order_id, UUID):
        raise OrderError("INVALID_INPUT", "Use a valid order ID.")


def validate_update(target: str, expected_version: int) -> None:
    validate_text(target, "the target status")
    if type(expected_version) is not int or expected_version < 0:
        raise OrderError("INVALID_INPUT", "Use a non-negative whole version.")


def check_transition(current: str, target: str) -> None:
    if current not in NEXT_STATUS or NEXT_STATUS[current] != target:
        raise OrderError("INVALID_TRANSITION", "Choose the next processing stage.")


def check_cancellation(current: str) -> None:
    if current == "CANCELLED":
        raise OrderError("ALREADY_CANCELLED", "This order has already been cancelled.")
    if current not in CANCELLABLE:
        raise OrderError("INVALID_TRANSITION", "Orders can only be cancelled before production.")


def check_version(current: int, expected: int) -> None:
    if current != expected:
        raise OrderError("STALE_VERSION", "This order changed. Refresh before continuing.")
