"""Validate and report Codex's explicitly self-authored reference review.

This is a consistency review with project context, never an independent public
chatbot observation or an accuracy benchmark. It does not run a model or
automatically determine whether legal reasoning is correct.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from env.public_chatbot_test import ROOT, question_set

ANSWERS = ROOT / "env/results/codex_self_eval_answers.json"
REPORT = ROOT / "env/results/codex_self_eval_report.md"


class SelfReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["consistent", "partial", "unresolved"]
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reason(self) -> SelfReview:
        if not self.reason.strip():
            raise ValueError("Review requires a nonempty reason")
        return self


class ReferenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer: str = Field(min_length=1)
    section_ids: list[str]
    sources: list[str] = Field(min_length=1)
    review: SelfReview

    @model_validator(mode="after")
    def validate_answer(self) -> ReferenceAnswer:
        if not self.answer.strip():
            raise ValueError("Answer must contain text")
        for source in self.sources:
            parsed = urlparse(source)
            if parsed.scheme != "https" or not parsed.netloc or any(char.isspace() for char in source):
                raise ValueError("Sources must be valid HTTPS links")
        if any(not section.strip() for section in self.section_ids):
            raise ValueError("Section ids must be nonempty")
        return self


class SelfEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_set: str
    question_set_version: int
    evaluation_type: Literal["self_authored_reference_review"]
    author: Literal["Codex"]
    reviewer: Literal["Codex (same assistant)"] = "Codex (same assistant)"
    context_access: str
    source_check_notes: str = "No independent current-law audit is claimed."
    captured_at: datetime
    answers: list[ReferenceAnswer]

    @model_validator(mode="after")
    def validate_evaluation(self) -> SelfEvaluation:
        questions = question_set()
        if (self.question_set, self.question_set_version) != (questions["id"], questions["version"]):
            raise ValueError("Question set and version must match the source fixture")
        if self.captured_at.utcoffset() is None:
            raise ValueError("Timestamp must include a time-zone offset")
        context = self.context_access.casefold()
        if "law pack" not in context or "answer key" not in context:
            raise ValueError("Context disclosure must include law pack and answer key access")
        expected = {question["id"] for question in questions["questions"]}
        actual = [answer.question_id for answer in self.answers]
        if len(actual) != len(expected) or len(set(actual)) != len(actual) or set(actual) != expected:
            raise ValueError("Exactly one answer for each of the ten known questions is required")
        return self


def load_evaluation(path: Path) -> SelfEvaluation:
    return SelfEvaluation.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_report(evaluation: SelfEvaluation) -> str:
    questions = question_set()["questions"]
    answers = {answer.question_id: answer for answer in evaluation.answers}
    lines = ["# Codex self-authored reference review", "",
             "Evaluation type: **self_authored_reference_review**.", "",
             f"Author and reviewer: **{evaluation.author}, the same assistant**. Captured: {evaluation.captured_at.isoformat()}.",
             f"Context seen: {evaluation.context_access.rstrip('.')}.", "",
             f"Source-check scope: {evaluation.source_check_notes}", "",
             "These answers were written and reviewed with the project's law pack and answer key in view. "
             "This is a reference consistency exercise, not an independent public-product test or an accuracy estimate. "
             "No ChatGPT/Gemini public responses or comparative accuracy scores are claimed.", "",
             "The review labels are the author's assessments, not automated proof of legal correctness.", "",
             "| Question | Topic | Self-review | Reason |", "| --- | --- | --- | --- |"]
    for question in questions:
        answer = answers[question["id"]]
        lines.append(f"| {question['id']} | {_cell(question['topic'])} | {answer.review.verdict} | {_cell(answer.review.reason)} |")
    lines += ["", "## Answers and sources", ""]
    for question in questions:
        answer = answers[question["id"]]
        lines += [f"### {question['id']}: {question['topic']}", "", answer.answer, "",
                  "Section identifiers: " + (", ".join(answer.section_ids) or "None; no binding provision asserted"), "",
                  f"Self-review: **{answer.review.verdict}** — {answer.review.reason}", ""]
        lines += [f"- [Source]({source})" for source in answer.sources]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path, default=ANSWERS)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    report = render_report(load_evaluation(args.answers))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote self-authored reference review: {args.output}")


if __name__ == "__main__":
    main()
