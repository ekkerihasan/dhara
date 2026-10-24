"""Transparent preference review with limited, conditional Karnataka screening."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from .legal import legal_findings, screen_jurisdiction
from .messages import draft_messages


SOURCES = [{
    "id": "mta-2021", "title": "Model Tenancy Act adoption announcement (PIB, 2 June 2021)",
    "url": "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1723636&lang=2&reg=48",
    "section": "Cabinet announcement; not a statutory section", "verified_on": "2026-10-18",
    "scope": "model_only", "applicable": False,
    "summary": "States and Union territories were invited to adopt the model through fresh legislation or amendments to existing rental laws.",
    "applicability_note": "Reference material only. No state enactment or applicability has been verified by this offline tool.",
}]


class ActionGuard:
    """Bound attempts and reject duplicate normalized actions."""
    def __init__(self, max_actions: int = 64):
        if max_actions < 1:
            raise ValueError("max_actions must be positive")
        self.max_actions = max_actions
        self.attempts = 0
        self.seen: set[str] = set()

    def allow(self, action: str, payload: object = None) -> bool:
        if self.attempts >= self.max_actions:
            return False
        self.attempts += 1
        key = json.dumps([action.strip().casefold(), payload], sort_keys=True, ensure_ascii=False)
        key = re.sub(r"\s+", " ", key)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


def extract_clauses(text: str) -> list[dict]:
    """Split numbered clauses or paragraphs, preserving page and line references."""
    if not isinstance(text, str):
        raise TypeError("Document text must be a string")
    result = []
    for page, content in enumerate(text.split("\f"), 1):
        current: list[str] = []
        start = 1
        def flush():
            if current:
                result.append({"id": f"C{len(result)+1}", "text": " ".join(current),
                               "page": page, "line": start})
                current.clear()
        for line_number, raw in enumerate(content.splitlines(), 1):
            line = raw.strip()
            if not line:
                flush()
                continue
            if re.match(r"^(?:\d+[.)]|clause\s+\d+\b)", line, re.I):
                flush()
            if not current:
                start = line_number
            current.append(line)
        flush()
    return result


def extract_document(path: str | Path) -> str:
    """Read a local document using the same extractor as browser uploads."""
    path = Path(path)
    from .documents import extract_bytes
    return extract_bytes(path.name, path.read_bytes())


def _preferences(preferences: dict | None) -> dict:
    preferences = dict(preferences or {})
    allowed = {"max_deposit_months", "max_notice_days", "min_notice_days", "max_rent_increase_percent", "max_refund_days", "min_entry_notice_hours"}
    unknown = set(preferences) - allowed
    if unknown:
        raise ValueError("Unknown preferences: " + ", ".join(sorted(unknown)))
    for key, value in preferences.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be a finite non-negative number")
    if preferences.get("min_notice_days", 0) > preferences.get("max_notice_days", float("inf")):
        raise ValueError("Minimum notice cannot exceed maximum notice")
    return preferences


def review_document(text: str, state: str = "", preferences: dict | None = None, facts: dict | None = None) -> dict:
    """Review preferences, ambiguities and narrowly scoped conditional legal risks.

    Preferences: max_deposit_months, max_notice_days, min_notice_days,
    max_rent_increase_percent, max_refund_days, min_entry_notice_hours.
    Numeric extraction supports digits only; unusual or non-English wording needs manual review.
    """
    prefs = _preferences(preferences)
    clauses = extract_clauses(text)
    jurisdiction = screen_jurisdiction(state, facts)
    state = state.strip()
    status = jurisdiction["status"]
    questions = list(jurisdiction["questions"])
    if not clauses:
        questions.insert(0, "Provide readable agreement text.")
    trace = [{"action": "extract_clauses", "status": "complete", "count": len(clauses)},
             {"action": "check_jurisdiction", "status": status, "state": state},
             {"action": "retrieve_sources", "status": "curated_retrieval", "source_ids": ["mta-2021"] + [s["id"] for s in jurisdiction["sources"]]}]
    findings: list[dict] = []
    guard = ActionGuard()
    rules = [
        ("deposit", "max_deposit_months", r"(\d+(?:\.\d+)?)\s*months?", "months of rent", "security deposit", "maximum"),
        ("notice", "max_notice_days", r"(\d+(?:\.\d+)?)\s*days?", "days", "notice period", "maximum"),
        ("notice", "min_notice_days", r"(\d+(?:\.\d+)?)\s*days?", "days", "notice period", "minimum"),
        ("increase", "max_rent_increase_percent", r"(\d+(?:\.\d+)?)\s*%", "%", "rent increase", "maximum"),
        ("refund", "max_refund_days", r"(\d+(?:\.\d+)?)\s*days?", "days", "deposit refund deadline", "maximum"),
        ("entry", "min_entry_notice_hours", r"(\d+(?:\.\d+)?)\s*hours?", "hours", "entry notice period", "minimum"),
    ]
    for clause in clauses:
        if not guard.allow("review_clause", clause["id"]):
            trace.append({"action": "review_clause", "status": "action_limit_reached"})
            break
        lowered = clause["text"].lower()
        for keyword, key, pattern, unit, label, direction in rules:
            if key not in prefs or keyword not in lowered:
                continue
            review_text = lowered
            if key in {"max_notice_days", "min_notice_days"}:
                # Access notice is a different obligation from ending a tenancy.
                access = r"\b(?:entry|enter|access|inspect(?:ion)?)\b"
                termination = r"\b(?:terminat\w*|vacat\w*|evict\w*|end(?:ing)?\s+(?:the\s+)?(?:lease|tenancy))\b"
                if re.search(access, lowered):
                    if not re.search(termination, lowered):
                        continue
                    # Mixed clauses can mention both obligations: use only
                    # explicit termination sentences, preserving uncertainty.
                    review_text = " ".join(sentence for sentence in re.split(r"(?<=[.;])\s+", lowered)
                                           if re.search(termination, sentence))
            values = re.findall(pattern, review_text)
            if len(values) != 1:
                findings.append(_finding(clause, "ambiguity", f"Confirm the {label} manually; a single numeric value could not be identified.", f"State the {label} clearly and confirm it meets your requested {direction} of {prefs[key]:g} {unit}.", key, prefs[key], direction))
            elif (float(values[0]) > prefs[key] if direction == "maximum" else float(values[0]) < prefs[key]):
                relation = "exceeds" if direction == "maximum" else "falls below"
                wording = "shall not exceed" if direction == "maximum" else "shall be at least"
                findings.append(_finding(clause, "preference", f"The {label} ({values[0]} {unit}) {relation} your requested {direction} ({prefs[key]:g} {unit}).", f"The {label} {wording} {prefs[key]:g} {unit}, subject to agreement and applicable law.", key, prefs[key], direction))
        if re.search(r"sole discretion|without (?:any )?notice|non[- ]refundable|as decided by", lowered):
            findings.append(_finding(clause, "ambiguity", "This wording leaves discretion or a potentially significant restriction that needs clarification.", "Please specify the conditions, amounts, deadlines, and responsibilities in writing before signing."))
        trace.append({"action": "review_clause", "status": "complete", "clause_id": clause["id"]})
    trace.append({"action": "review_preferences", "status": "complete" if len(clauses) <= guard.max_actions else "partial", "reviewed_clauses": min(len(clauses), guard.max_actions)})
    findings.extend(legal_findings(clauses[:guard.max_actions], jurisdiction))
    trace.append({"action": "draft_messages", "status": "complete"})
    return {"status": status, "state": state, "clauses": clauses, "findings": findings,
            "questions": questions, "sources": [dict(s) for s in SOURCES] + jurisdiction["sources"], "trace": trace,
            "preferences": prefs, "jurisdiction": jurisdiction,
            "messages": draft_messages(findings),
            "limitations": ["Legal screening is limited to encoded Karnataka exclusions and a conditional essential-services rule; it is not a complete legal opinion.",
                            "Deterministic English numeric-pattern review; findings are not exhaustive.",
                            "Only the first 64 clauses are reviewed; extracted clauses remain visible."]}


def _finding(clause: dict, category: str, explanation: str, revision: str, rule=None, limit=None, direction=None) -> dict:
    return {"clause_id": clause["id"], "page": clause["page"], "line": clause["line"],
            "original": clause["text"], "category": category, "explanation": explanation,
            "proposed_revision": revision, "citations": [], "rule": rule, "limit": limit, "direction": direction}
