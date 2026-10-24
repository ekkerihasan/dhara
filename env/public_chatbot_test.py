"""Capture and report the ten-question public-chatbot side test honestly.

This imports recorded responses; it does not query chatbot websites or grade
legal meaning automatically. Codex reference answers never earn public-test credit.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "env/tasks/public_chatbot_questions.json"
ANSWERS = ROOT / "env/results/public_chatbot_answers.json"
REPORT = ROOT / "env/results/public_chatbot_report.md"
SERVICES = ("ChatGPT", "Gemini")


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["correct", "partial", "incorrect", "unverified"]
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)
    wrong_law: bool = False

    @model_validator(mode="after")
    def validate_review(self) -> Review:
        if not self.reviewer.strip() or not self.reason.strip():
            raise ValueError("Review needs a named reviewer and explanation")
        if any(not source.startswith("https://") for source in self.sources):
            raise ValueError("Review sources must be HTTPS links")
        if self.wrong_law and self.verdict not in {"partial", "incorrect"}:
            raise ValueError("A wrong-law finding cannot be marked correct or unverified")
        return self


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: Literal["ChatGPT", "Gemini", "Codex"]
    question_id: str
    access_method: Literal["public_web", "self_reference"]
    model: str | None = None
    captured_at: datetime | None = None
    browsing: Literal["on", "off", "unknown"] = "unknown"
    batch: bool = False
    raw_answer: str | None = None
    evidence: str | None = None
    review: Review | None = None

    @model_validator(mode="after")
    def validate_capture(self) -> Answer:
        expected_method = "self_reference" if self.service == "Codex" else "public_web"
        if self.access_method != expected_method:
            raise ValueError("Do not label API or Codex output as a public-chatbot response")
        if self.raw_answer is None:
            if self.review is not None:
                raise ValueError("A missing answer cannot receive a review")
            return self
        if not self.raw_answer.strip():
            raise ValueError("An answer must be nonempty; use null for not run")
        if not self.model or not self.model.strip() or not self.evidence or not self.evidence.strip():
            raise ValueError("Captured answers need model metadata and transcript/share-link evidence")
        if self.captured_at is None or self.captured_at.utcoffset() is None:
            raise ValueError("Capture timestamp must include a time-zone offset")
        if self.service == "Codex" and self.review is not None:
            raise ValueError("Reference answers cannot be scored as independent observations")
        return self


def question_set() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def blank_answers() -> dict:
    questions = question_set()
    return {"question_set": questions["id"], "question_set_version": questions["version"],
            "answers": [Answer(service=service, question_id=q["id"], access_method="public_web").model_dump(mode="json")
                        for service in SERVICES for q in questions["questions"]]}


def load_answers(path: Path) -> list[Answer]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = question_set()
    if (payload.get("question_set"), payload.get("question_set_version")) != (questions["id"], questions["version"]):
        raise ValueError("Answers must name the exact question set and version")
    answers = [Answer.model_validate(row) for row in payload["answers"]]
    _validate_records(answers)
    return answers


def _validate_records(answers: list[Answer]) -> None:
    questions = question_set()
    known_ids = {q["id"] for q in questions["questions"]}
    seen: set[tuple[str, str]] = set()
    for answer in answers:
        key = (answer.service, answer.question_id)
        if answer.question_id not in known_ids or key in seen:
            raise ValueError("Unknown question id or duplicate service/question response")
        seen.add(key)


def render_report(answers: list[Answer]) -> str:
    _validate_records(answers)
    questions = question_set()["questions"]
    indexed = {(a.service, a.question_id): a for a in answers}
    observed = [a for a in answers if a.service in SERVICES and a.raw_answer is not None]
    reviewed = [a for a in observed if a.review is not None]
    total = len(SERVICES) * len(questions)
    complete = len(reviewed) == total
    lines = ["# Public chatbot side test", "",
             "Status: **complete**." if complete else "Status: **incomplete — actual public responses and reviews are still required**.", "",
             f"Captured public responses: **{len(observed)}/{total}**. Reviewed: **{len(reviewed)}/{total}**.", "",
             "Codex reference answers are excluded from all counts. An unanswered question is not a pass or a chatbot failure.", "",
             "| Question | ChatGPT | Gemini |", "| --- | --- | --- |"]
    for question in questions:
        cells = []
        for service in SERVICES:
            answer = indexed.get((service, question["id"]))
            if answer is None or answer.raw_answer is None:
                cells.append("Not run")
            elif answer.review is None:
                cells.append("Captured; not reviewed")
            else:
                cells.append(answer.review.verdict + ("; wrong law" if answer.review.wrong_law else ""))
        lines.append(f"| {question['id']}: {question['topic']} | {' | '.join(cells)} |")
    if complete:
        lines += ["", "## Reviewed observations", ""]
        for service in SERVICES:
            rows = [a for a in reviewed if a.service == service]
            correct = sum(a.review.verdict == "correct" for a in rows)
            wrong = sum(a.review.wrong_law for a in rows)
            lines.append(f"- {service}: {correct}/{len(questions)} classified correct; {wrong} wrong-law findings.")
    lines += ["", "## Evidence and review notes", ""]
    for answer in observed:
        lines += [f"### {answer.service} / {answer.question_id}", "",
                  f"Model: {answer.model}. Captured: {answer.captured_at.isoformat()}. Browsing: {answer.browsing}. Batch: {answer.batch}.",
                  f"Evidence: {answer.evidence}", ""]
        lines += ["> " + line for line in answer.raw_answer.splitlines()]
        if answer.review:
            lines += ["", f"Review by {answer.review.reviewer}: {answer.review.reason}"]
            lines += [f"- [Review source]({url})" for url in answer.review.sources]
        lines.append("")
    lines += ["This is a small, selected question set, not a general legal-accuracy estimate.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "report"))
    parser.add_argument("--answers", type=Path, default=ANSWERS)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    if args.command == "init":
        args.answers.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite answers someone has already collected.
        with args.answers.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(blank_answers(), ensure_ascii=False, indent=2) + "\n")
        print(f"Created response template: {args.answers}")
    else:
        report = render_report(load_answers(args.answers))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8", newline="\n")
        print(report)


if __name__ == "__main__":
    main()
