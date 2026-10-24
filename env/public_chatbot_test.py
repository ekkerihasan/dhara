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


def render_prompts(question_id: str | None = None) -> str:
    """Export only test inputs; never leak the answer key to the chatbot."""
    questions = question_set()
    selected = [q for q in questions["questions"] if question_id is None or q["id"] == question_id]
    if not selected:
        raise ValueError("Unknown question id")
    lines = [questions["common_instruction"], ""]
    if question_id is None:
        lines += ["Answer each question separately under its Q identifier, at most 150 words per answer.", ""]
    for question in selected:
        lines += [question["id"], question["question"], ""]
    return "\n".join(lines)


def record_answer(path: Path, answer: Answer) -> None:
    """Validate before writing and refuse to replace an existing observation."""
    if answer.service not in SERVICES or answer.raw_answer is None:
        raise ValueError("Record requires an actual public response")
    answers = load_answers(path)
    for index, previous in enumerate(answers):
        if (previous.service, previous.question_id) == (answer.service, answer.question_id):
            if previous.raw_answer is not None:
                raise ValueError("Response already captured; refusing to overwrite")
            answers[index] = answer
            break
    else:
        answers.append(answer)
    _validate_records(answers)
    questions = question_set()
    payload = {"question_set": questions["id"], "question_set_version": questions["version"],
               "answers": [row.model_dump(mode="json") for row in answers]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


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
    parser.add_argument("command", choices=("init", "report", "prompts", "record"))
    parser.add_argument("--answers", type=Path, default=ANSWERS)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--question", help="Q01–Q10; omit for a batch prompt")
    parser.add_argument("--service", choices=SERVICES)
    parser.add_argument("--raw-answer", type=Path, help="UTF-8 file containing the verbatim public answer")
    parser.add_argument("--model", help="Displayed model, or 'not displayed'")
    parser.add_argument("--captured-at", help="Actual capture timestamp including time-zone offset")
    parser.add_argument("--evidence", help="Share URL or saved transcript path")
    parser.add_argument("--browsing", choices=("on", "off", "unknown"), default="unknown")
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()
    if args.command == "prompts":
        print(render_prompts(args.question))
    elif args.command == "record":
        if not all((args.service, args.question, args.raw_answer, args.model, args.captured_at, args.evidence)):
            parser.error("record requires --service, --question, --raw-answer, --model, --captured-at and --evidence")
        answer = Answer(service=args.service, question_id=args.question, access_method="public_web",
                        model=args.model, captured_at=args.captured_at, evidence=args.evidence,
                        browsing=args.browsing, batch=args.batch,
                        raw_answer=args.raw_answer.read_text(encoding="utf-8-sig"))
        record_answer(args.answers, answer)
        print(f"Recorded {answer.service} / {answer.question_id}; source-backed review still required")
    elif args.command == "init":
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
