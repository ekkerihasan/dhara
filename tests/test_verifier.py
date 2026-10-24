import pytest
from pydantic import ValidationError

from backend.agent.verifier import verify_claims


@pytest.mark.parametrize("text,section_id,expected", [
    ("Section 74 concerns reasonable compensation.", "ICA-74", "cited"),
    ("The law caps deposits at two months.", "MTA-11(1)", "blocked"),
    ("Use the Rent Authority.", "MTA-30", "blocked"),
    ("The law caps deposits.", "fake", "blocked"),
    ("A statutory cap applies.", None, "blocked"),
    ("You are entitled to a receipt.", None, "blocked"),
    ("Under s. 49 services are protected.", None, "blocked"),
    ("Please discuss the painting charge.", None, "unverified"),
])
def test_verifier(text: str, section_id: str | None, expected: str) -> None:
    result = verify_claims([{"text": text, "section_id": section_id}])[0]
    assert result.verdict == expected
    assert result.text == text


def test_rejects_unexpected_claim_fields() -> None:
    with pytest.raises(ValidationError):
        verify_claims([{"text": "hello", "verdict": "cited"}])
