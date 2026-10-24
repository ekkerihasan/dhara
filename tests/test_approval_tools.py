from datetime import date

import pytest

from backend.tools.messages import SCHEDULED, send_and_schedule


@pytest.mark.parametrize("approval", [False, None, "true", 1])
def test_requires_explicit_approval(approval: object) -> None:
    before = len(SCHEDULED)
    with pytest.raises(PermissionError):
        send_and_schedule("Hello", approval)
    assert len(SCHEDULED) == before


def test_records_followup_without_claiming_delivery() -> None:
    result = send_and_schedule("Please reconsider.", True, today=date(2026, 10, 24))
    try:
        assert result["follow_up_date"] == "2026-10-31"
        assert result["delivery_status"] == "not_sent"
        result["message"] = "mutated"
        assert SCHEDULED[result["id"]]["message"] == "Please reconsider."
    finally:
        SCHEDULED.pop(result["id"])


def test_empty_message_is_not_scheduled() -> None:
    with pytest.raises(ValueError):
        send_and_schedule("", True)
