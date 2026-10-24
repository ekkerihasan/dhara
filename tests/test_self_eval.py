"""Synthetic fixtures exercise provenance guards, never represent captured answers."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from env.public_chatbot_test import question_set
from env.self_eval import ANSWERS, SelfEvaluation, load_evaluation, render_report


def fixture() -> dict:
    questions = question_set()
    return {"question_set": questions["id"], "question_set_version": questions["version"],
            "evaluation_type": "self_authored_reference_review", "author": "Codex",
            "context_access": "law pack and answer key", "captured_at": "2026-10-25T07:00:00+05:30",
            "answers": [{"question_id": question["id"], "answer": "Synthetic unit-test answer.",
                         "section_ids": [], "sources": ["https://example.org/synthetic-test-source"],
                         "review": {"verdict": "unresolved", "reason": "Synthetic fixture only."}}
                        for question in questions["questions"]]}


def test_report_has_ten_reviews_and_explicit_self_review_disclosure(tmp_path: Path) -> None:
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(fixture()), encoding="utf-8")
    report = render_report(load_evaluation(path))
    assert report.count("| unresolved |") == 10
    assert "the same assistant" in report
    assert "answer key in view" in report
    assert "not an independent public-product test" in report
    assert "accuracy estimate" in report
    assert "%" not in report


def test_committed_answers_cover_all_questions_with_bounded_answers_and_known_sections() -> None:
    from backend.tools.law import lookup_section

    evaluation = load_evaluation(ANSWERS)
    assert len(evaluation.answers) == 10
    for answer in evaluation.answers:
        assert len(answer.answer.split()) <= 150
        assert all(lookup_section(section) is not None for section in answer.section_ids)
    assert "same assistant" in evaluation.reviewer


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unknown"])
def test_exactly_ten_distinct_known_answers_required(failure: str) -> None:
    payload = fixture()
    if failure == "missing":
        payload["answers"].pop()
    elif failure == "duplicate":
        payload["answers"][-1] = deepcopy(payload["answers"][0])
    else:
        payload["answers"][-1]["question_id"] = "Q99"
    with pytest.raises(ValidationError):
        SelfEvaluation.model_validate(payload)


@pytest.mark.parametrize("field,value", [("evaluation_type", "independent_public_test"),
                                        ("author", "ChatGPT"), ("context_access", "none"),
                                        ("captured_at", "2026-10-25T07:00:00"),
                                        ("question_set_version", 999)])
def test_cannot_relabel_reference_review_or_hide_context(field: str, value: object) -> None:
    payload = fixture()
    payload[field] = value
    with pytest.raises(ValidationError):
        SelfEvaluation.model_validate(payload)


@pytest.mark.parametrize("field,value", [("answer", "  "), ("sources", []),
                                        ("sources", ["http://example.org"]),
                                        ("sources", ["https://"]),
                                        ("access_method", "public_web")])
def test_answer_requires_text_and_https_sources_and_rejects_public_metadata(field: str, value: object) -> None:
    payload = fixture()
    payload["answers"][0][field] = value
    with pytest.raises(ValidationError):
        SelfEvaluation.model_validate(payload)
