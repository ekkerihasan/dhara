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


def test_agent_findings_get_clause_specific_asks() -> None:
    findings = [{"clause_ref": "C2", "category": "deposit_forfeiture", "issue": "model prose"},
                {"clause_ref": "C5", "category": "rent_escalation_excess"}]
    en = draft_message(findings, "request", "en")["text"]
    assert "- C2: please replace forfeiture of the whole deposit" in en and "s.74" in en
    assert "- C5: please revise the yearly rent increase to 10%." in en
    assert "Please clarify the conditions" not in en and "model prose" not in en
    kn = draft_message(findings, "request", "kn")["text"]
    assert "ಸೆಕ್ಷನ್ 74" in kn and "C5" in kn


def test_moveout_challenge_and_notice() -> None:
    findings = [{"clause_ref": "C4", "category": "wear_and_tear"}]
    challenge = draft_message(findings, "challenge", "en")["text"]
    assert challenge.startswith("Regarding the deductions") and "s.108(m)" in challenge
    assert draft_message(findings, "notice", "en")["text"].startswith("I am following up")
