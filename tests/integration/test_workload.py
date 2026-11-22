from datetime import UTC, datetime, timedelta, timezone

import pytest

from orderflow.models import OrderError, Principal
from orderflow.rules import pickup_is_overdue

SAM = Principal("staff-s")
ALEX = Principal("customer-a")


@pytest.mark.parametrize(("seconds", "expected"), [(172799, False), (172800, True), (172801, True)])
def test_t29_elapsed_time_across_offsets(seconds, expected):
    singapore = timezone(timedelta(hours=8))
    ready = datetime(2026, 11, 20, 0, 0, tzinfo=singapore)
    observed = datetime(2026, 11, 19, 16, 0, tzinfo=UTC) + timedelta(seconds=seconds)
    assert pickup_is_overdue(ready, observed) is expected


def test_t29_queue_ages_from_ready_event(service):
    order = service.create_order(ALEX, service_id="bw-print", quantity=1)
    for stage in ("CONFIRMED", "PROCESSING", "READY_FOR_PICKUP"):
        order = service.advance_order(SAM, order.id, target=stage, expected_version=order.version)
    before = service.get_order(ALEX, order.id)
    due = before.history[-1].occurred_at + timedelta(hours=48)
    assert service.staff_queue(SAM, as_of=due - timedelta(microseconds=1)) == ([order], set())
    assert service.customer_queue(ALEX, as_of=due - timedelta(microseconds=1)) == ([order], set())
    assert service.customer_queue(ALEX, as_of=due) == ([order], {order.id})
    assert service.customer_queue(Principal("customer-b"), as_of=due) == ([], set())
    for _ in range(2):
        assert service.staff_queue(SAM, as_of=due) == ([order], {order.id})
    assert service.get_order(ALEX, order.id) == before


@pytest.mark.parametrize(("actor", "code"), [(ALEX, "FORBIDDEN"), (None, "UNAUTHENTICATED")])
def test_t30_staff_queue_access(service, actor, code):
    with pytest.raises(OrderError) as error:
        service.staff_queue(actor, as_of=datetime.now(UTC))
    assert error.value.code == code
