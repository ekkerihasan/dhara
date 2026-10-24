import pytest

from backend.tools.messages import draft_message


@pytest.mark.parametrize("tone", ["request", "challenge", "notice"])
@pytest.mark.parametrize("language", ["en", "kn"])
def test_draft_reuses_templates(tone: str, language: str) -> None:
    result = draft_message([{"clause_ref": "C2", "category": "deposit_forfeiture", "text": "Arbitrary model prose"}], tone, language)
    assert result["tone"] == tone
    assert result["language"] == language
    assert "C2" in result["text"]
    assert "Arbitrary model prose" not in result["text"]
    if language == "kn":
        assert any("\u0c80" <= character <= "\u0cff" for character in result["text"])


def test_invalid_language_or_tone() -> None:
    with pytest.raises(ValueError):
        draft_message([], language="hi")
    with pytest.raises(ValueError):
        draft_message([], tone="threaten")
