"""Deterministic EN/KN requests built on the prototype templates."""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any
from uuid import uuid4

from housing.messages import draft_messages

LOGGER = logging.getLogger(__name__)
SCHEDULED: dict[str, dict[str, str]] = {}
HEADERS = {
    "challenge": {"en": "Please reconsider the proposed deductions and provide an itemised explanation with supporting evidence.",
                  "kn": "ಪ್ರಸ್ತಾಪಿತ ಕಡಿತಗಳನ್ನು ದಯವಿಟ್ಟು ಮರುಪರಿಶೀಲಿಸಿ ಮತ್ತು ಪುರಾವೆಗಳೊಂದಿಗೆ ವಿವರವಾದ ಲೆಕ್ಕವನ್ನು ನೀಡಿ."},
    "notice": {"en": "I am following up on my earlier request. Please respond in writing within seven days so we can resolve the outstanding amount.",
               "kn": "ನನ್ನ ಹಿಂದಿನ ವಿನಂತಿಯನ್ನು ಮತ್ತೆ ನೆನಪಿಸುತ್ತಿದ್ದೇನೆ. ಬಾಕಿ ಮೊತ್ತವನ್ನು ಪರಿಹರಿಸಲು ದಯವಿಟ್ಟು ಏಳು ದಿನಗಳಲ್ಲಿ ಲಿಖಿತ ಉತ್ತರ ನೀಡಿ."},
}


def draft_message(findings: list[dict[str, Any]], tone: str = "request", language: str = "en") -> dict[str, str]:
    """Use prototype templates; arbitrary source prose is never called translated."""
    if tone not in {"request", "challenge", "notice"} or language not in {"en", "kn"}:
        raise ValueError("Choose request/challenge/notice and en/kn")
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ValueError("findings must be a list of objects")
    # Pass only structured fields to templates; no model prose is sent as if it
    # had been translated. Keep numerical preference requests where supported.
    safe = [{key: finding[key] for key in ("clause_id", "category", "rule", "limit", "direction") if key in finding}
            | {"clause_id": finding.get("clause_ref", finding.get("clause_id", "?"))}
            for finding in findings]
    messages = draft_messages(safe)
    text = messages["english" if language == "en" else "kannada"]
    if tone != "request":
        text = HEADERS[tone][language] + "\n\n" + text
    LOGGER.info("draft_message tone=%s language=%s findings=%s", tone, language, len(findings))
    return {"text": text, "language": language, "tone": tone, "translation_note": messages["translation_note"]}


def send_and_schedule(message: str, approved: bool, *, today: date | None = None) -> dict[str, str]:
    """Record an approved draft and follow-up; no external delivery is configured."""
    if approved is not True:
        raise PermissionError("Explicit tenant approval is required")
    if not isinstance(message, str) or not message.strip() or len(message) > 20000:
        raise ValueError("Provide a nonempty message of at most 20,000 characters")
    id = str(uuid4())
    record = {"id": id, "message": message, "status": "scheduled", "delivery_status": "not_sent",
              "follow_up_date": ((today or date.today()) + timedelta(days=7)).isoformat()}
    SCHEDULED[id] = record.copy()
    LOGGER.info("send_and_schedule id=%s approved=true", id)
    return record
