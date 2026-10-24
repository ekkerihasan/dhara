import pytest

from backend.tools.messages import draft_message


@pytest.mark.parametrize("tone", ["request", "challenge", "notice"])
@pytest.mark.parametrize("language", ["en", "kn", "hi"])
def test_draft_reuses_templates(tone: str, language: str) -> None:
    result = draft_message([{"clause_ref": "C2", "category": "deposit_forfeiture", "text": "Arbitrary model prose"}], tone, language)
    assert result["tone"] == tone
    assert result["language"] == language
    assert "C2" in result["text"]
    assert "Arbitrary model prose" not in result["text"]
    if language == "kn":
        assert any("\u0c80" <= character <= "\u0cff" for character in result["text"])
    if language == "hi":
        assert any("ऀ" <= character <= "ॿ" for character in result["text"])


def test_invalid_language_or_tone() -> None:
    with pytest.raises(ValueError):
        draft_message([], language="ta")
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


def test_indian_digit_grouping_and_agreed_letter() -> None:
    from backend.tools.messages import draft_message, inr
    assert [inr(n) for n in (0, 999, 8000, 80396, 150000, 12345678)] == ["0", "999", "8,000", "80,396", "1,50,000", "1,23,45,678"]
    items = [{"clause_ref": "C4", "category": "painting_or_cleaning_fixed", "terms": {"painting_inr": 8000}, "settled": True},
             {"clause_ref": "C3", "category": "lock_in", "terms": {"lock_in_months": 3}, "settled": False},
             {"clause_ref": "C5", "category": None, "terms": {"notice_hours": 24}, "settled": False}]
    english = draft_message(items, "request", "en")["text"]
    assert "C4 (agreed): an exit painting or cleaning charge of at most Rs 8,000." in english
    assert "C3: please cap the early-exit payment" in english
    assert "C5: the landlord enters only after at least 24 hours' written notice." in english
    for language in ("kn", "hi"):
        text = draft_message(items, "request", language)["text"]
        assert "8,000" in text and "24" in text and "{" not in text
