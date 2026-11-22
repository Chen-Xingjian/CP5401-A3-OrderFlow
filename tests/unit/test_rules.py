from itertools import product

import pytest

from orderflow.models import OrderError
from orderflow.rules import check_transition, validate_creation, validate_update

# R1-01 is the oracle. Keep the expected flow independent of the implementation table.
STAGES = ["PENDING", "CONFIRMED", "PROCESSING", "READY_FOR_PICKUP", "COMPLETED"]


@pytest.mark.parametrize("quantity", [1, 99])
@pytest.mark.parametrize("note", ["", "x" * 500])
def test_t02_accept_boundaries(quantity, note):
    validate_creation("bw-print", quantity, note)


@pytest.mark.parametrize("quantity", [0, 100, -1, True, False, 1.5, None, "2"])
def test_t02_reject_quantity(quantity):
    with pytest.raises(OrderError) as error:
        validate_creation("bw-print", quantity, "")
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("note", ["x" * 501, 1, None, "broken\x00text", "\ud800"])
def test_t02_reject_note(note):
    with pytest.raises(OrderError) as error:
        validate_creation("bw-print", 1, note)
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("current,target", list(product(STAGES, [*STAGES, "UNKNOWN"])))
def test_t10_t11_t13_transition_matrix(current, target):
    if (current, target) in list(zip(STAGES[:-1], STAGES[1:], strict=True)):
        check_transition(current, target)
    else:
        with pytest.raises(OrderError) as error:
            check_transition(current, target)
        assert error.value.code == "INVALID_TRANSITION"


@pytest.mark.parametrize("version", [None, True, -1, "0", 0.5])
def test_invalid_version(version):
    with pytest.raises(OrderError) as error:
        validate_update("CONFIRMED", version)
    assert error.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("status", ["PENDING", "CONFIRMED"])
def test_t21_cancellation_is_separate_from_staff_progress(status):
    from orderflow.rules import check_cancellation

    check_cancellation(status)
    with pytest.raises(OrderError) as error:
        check_transition(status, "CANCELLED")
    assert error.value.code == "INVALID_TRANSITION"


@pytest.mark.parametrize(
    "status,code",
    [
        ("PROCESSING", "INVALID_TRANSITION"),
        ("READY_FOR_PICKUP", "INVALID_TRANSITION"),
        ("COMPLETED", "INVALID_TRANSITION"),
        ("CANCELLED", "ALREADY_CANCELLED"),
    ],
)
def test_t22_t24_cancellation_denials(status, code):
    from orderflow.rules import check_cancellation

    with pytest.raises(OrderError) as error:
        check_cancellation(status)
    assert error.value.code == code
