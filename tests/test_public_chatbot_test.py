import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from env.public_chatbot_test import Answer, Review, blank_answers, load_answers, record_answer, render_prompts, render_report


def capture(**overrides: object) -> dict:
    return {"service": "ChatGPT", "question_id": "Q01", "access_method": "public_web",
            "model": "not displayed", "captured_at": "2026-10-24T22:00:00+05:30",
            "raw_answer": "Synthetic test response, not a real captured chatbot answer.",
            "evidence": "tests/fixtures/synthetic-response.txt", **overrides}


def review(**overrides: object) -> dict:
    return {"verdict": "correct", "reviewer": "Synthetic unit-test reviewer", "reason": "Unit-test fixture only",
            "sources": ["https://example.org/synthetic-source"], **overrides}


def test_missing_answers_never_count_as_passes() -> None:
    answers = [Answer.model_validate(row) for row in blank_answers()["answers"]]
    report = render_report(answers)
    assert "**0/20**" in report
    assert "**incomplete" in report
    assert "classified correct" not in report
    assert report.count("Not run") == 20


def test_reference_answers_are_excluded_and_cannot_be_self_scored() -> None:
    reference = capture(service="Codex", access_method="self_reference")
    assert "**0/20**" in render_report([Answer.model_validate(reference)])
    with pytest.raises(ValidationError):
        Answer.model_validate({**reference, "review": review()})
    with pytest.raises(ValidationError):
        Answer.model_validate(capture(service="Codex"))


@pytest.mark.parametrize("overrides", [{"model": None}, {"captured_at": None}, {"captured_at": "2026-10-24T22:00:00"},
                                      {"evidence": None}, {"raw_answer": "  "}, {"access_method": "self_reference"}])
def test_real_capture_requires_provenance(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        Answer.model_validate(capture(**overrides))


def test_cannot_review_a_missing_answer_or_label_wrong_law_correct() -> None:
    with pytest.raises(ValidationError):
        Answer.model_validate(capture(raw_answer=None, review=review()))
    with pytest.raises(ValidationError):
        Review.model_validate(review(wrong_law=True))
    with pytest.raises(ValidationError):
        Review.model_validate(review(sources=[]))


def test_only_all_twenty_captured_and_reviewed_responses_complete_the_report() -> None:
    answers = [Answer.model_validate(capture(service=row["service"], question_id=row["question_id"], review=review()))
               for row in blank_answers()["answers"]]
    assert "Status: **complete**" in render_report(answers)
    assert "Status: **incomplete" in render_report(answers[:-1])
    answers[0] = Answer.model_validate(capture())
    assert "Captured; not reviewed" in render_report(answers)
    assert "Status: **incomplete" in render_report(answers)


@pytest.mark.parametrize("bad_id,duplicate", [("unknown", False), ("Q01", True)])
def test_unknown_or_duplicate_question_records_rejected(tmp_path: Path, bad_id: str, duplicate: bool) -> None:
    payload = blank_answers()
    if duplicate:
        payload["answers"].append(payload["answers"][0])
    else:
        payload["answers"][0]["question_id"] = bad_id
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_answers(path)


def test_prompt_export_does_not_contaminate_test_with_answer_key() -> None:
    from env.public_chatbot_test import question_set

    batch = render_prompts()
    for question in question_set()["questions"]:
        assert question["question"] in batch
        assert question["answer_key"] not in batch
        assert question["wrong_law_trap"] not in batch
    single = render_prompts("Q01")
    assert "Q01" in single
    assert "Q02" not in single
    with pytest.raises(ValueError, match="Unknown"):
        render_prompts("Q99")


def test_record_preserves_other_rows_and_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(blank_answers()), encoding="utf-8")
    answer = Answer.model_validate(capture())
    record_answer(path, answer)
    rows = load_answers(path)
    assert len(rows) == 20
    assert rows[0].raw_answer == answer.raw_answer
    assert sum(row.raw_answer is not None for row in rows) == 1
    before = path.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        record_answer(path, answer)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="Unknown"):
        record_answer(path, Answer.model_validate(capture(question_id="Q99")))
    assert path.read_bytes() == before
