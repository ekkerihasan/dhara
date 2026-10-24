"""Curated legal retrieval and conservative Karnataka applicability screening.

This small ruleset does not replace a determination by a competent authority.
Current rent alone never establishes the statutory rent exclusion.
"""
from __future__ import annotations

from datetime import date
import math
import re

ACT_URL = "https://www.indiacode.nic.in/bitstream/123456789/7810/1/34_of_2001_e.pdf"
SOURCES = [
    {"id": "ka-rent-s2", "title": "Karnataka Rent Act, 1999", "section": "2(1)-(3)",
     "url": ACT_URL + "#page=7", "verified_on": "2026-10-18", "scope": "applicability",
     "summary": "Coverage depends on scheduled areas, ownership, statutory rent and construction or substantial renovation exemptions.",
     "supporting_passage": "Paraphrase: section 2 excludes specified ownership classes, statutory rents above area thresholds, and premises during a fifteen-year construction/renovation period.",
     "verification_method": "Official India Code consolidated document, indexed section text checked; PDF server intermittently times out."},
    {"id": "ka-rent-s49", "title": "Karnataka Rent Act, 1999", "section": "49(1)",
     "url": ACT_URL + "#page=45", "verified_on": "2026-10-18", "scope": "conditional_rule",
     "summary": "If the Act applies, essential services cannot be withheld without just and sufficient cause.",
     "supporting_passage": "without just and sufficient cause cut off or withhold",
     "verification_method": "Official India Code indexed section 49 text checked."},
]


def _number(value, name):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return value


def screen_jurisdiction(state: str, facts: dict | None = None) -> dict:
    if not isinstance(state, str) or (facts is not None and not isinstance(facts, dict)):
        raise ValueError("State must be text and property facts must be an object")
    facts = dict(facts or {})
    for key in ("monthly_rent", "standard_rent_monthly", "building_age_years"):
        if key in facts:
            facts[key] = _number(facts[key], key)
    for key in ("residential", "other_exemptions_checked"):
        if key in facts and facts[key] is not None and not isinstance(facts[key], bool):
            raise ValueError(f"{key} must be true or false")
    tenancy_date = facts.get("tenancy_date")
    if tenancy_date:
        try:
            date.fromisoformat(tenancy_date)
        except (ValueError, TypeError) as exc:
            raise ValueError("Tenancy date must use YYYY-MM-DD") from exc
    state = state.strip()
    result = {"status": "applicability_unresolved", "questions": [], "reasons": [],
              "facts": facts, "sources": [], "conditional_rules_enabled": False,
              "note": "Coverage is screened from user-provided facts; judicial interpretation and undisclosed exemptions are not verified."}
    if not state:
        result.update(status="needs_jurisdiction", questions=["Which state and city is the property in?"])
        return result
    if state.casefold() != "karnataka":
        result.update(status="unsupported_jurisdiction", questions=["This version supports Karnataka residential screening only; obtain the applicable state-law review."])
        return result
    result["sources"] = [dict(source, applicable=False) for source in SOURCES]
    ownership = facts.get("ownership_type", "unknown")
    if ownership in {"government", "religious_charitable", "wakf", "cooperative", "market_committee", "government_grant"}:
        result.update(status="rent_act_excluded", reasons=["The stated ownership or grant falls within section 2(3) exclusions."])
        return result
    age = facts.get("building_age_years")
    if age is not None and age < 15:
        result.update(status="rent_act_excluded", reasons=["The stated construction/substantial-renovation age is below the section 2(3)(f) fifteen-year period."])
        return result
    area = facts.get("schedule_area", "unknown")
    rent = facts.get("standard_rent_monthly")
    threshold = 3500 if area == "part_a" else 2000 if area == "other_scheduled" else None
    if threshold is not None and rent is not None and rent > threshold:
        result.update(status="rent_act_excluded", reasons=[f"The stated statutory deemed/standard rent exceeds the section 2(3)(e) threshold of INR {threshold}; current market rent was not used."])
        return result
    questions = result["questions"]
    if not isinstance(facts.get("city"), str) or not facts["city"].strip():
        questions.append("Confirm the property city and scheduled area.")
    if facts.get("residential") is not True:
        questions.append("Confirm residential use; commercial premises need a separate applicability review.")
    if ownership != "private":
        questions.append("Confirm private ownership and absence of the section 2(3) ownership/grant exclusions.")
    if age is None:
        questions.append("Confirm years since construction or substantial renovation.")
    if threshold is None:
        questions.append("Verify whether the premises are in Part A or another relevant scheduled area; city name alone is insufficient.")
    if rent is None:
        questions.append("Obtain the statutory deemed/standard rent under section 2(3)(e), not simply current monthly rent.")
    if not tenancy_date or tenancy_date < "2001-12-31":
        questions.append("Confirm a tenancy date on/after commencement; earlier tenancies need separate analysis.")
    if facts.get("other_exemptions_checked") is not True:
        questions.append("Confirm other section 2 exemptions and relevant notifications have been checked.")
    if not questions:
        result.update(status="conditional_legal_review", conditional_rules_enabled=True,
                      reasons=["No encoded section 2 exclusion was found in the supplied facts; legal findings remain conditional on those facts."])
        result["sources"] = [dict(source, applicable="conditional") for source in SOURCES]
    return result


def legal_findings(clauses: list[dict], jurisdiction: dict) -> list[dict]:
    if not jurisdiction["conditional_rules_enabled"]:
        return []
    findings = []
    for clause in clauses:
        text = clause["text"].casefold()
        services = re.search(r"\b(?:water|electricity|power|essential service[s]?)\b", text)
        deprivation = re.search(r"cut\s*off|disconnect|withhold|stop (?:the )?supply", text)
        if services and deprivation:
            # Preserve prohibitions/exceptions for human interpretation, rather
            # than declaring every mention of disconnection a violation.
            if re.search(r"(?:shall|must|may) not|cannot|prohibited|no landlord", text):
                continue
            findings.append({"clause_id": clause["id"], "page": clause["page"], "line": clause["line"],
                "original": clause["text"], "category": "potential_legal_conflict",
                "explanation": "Potential section 49(1) conflict: the clause permits essential-service withdrawal. This requires just and sufficient cause where the Act applies; obtain human review of the facts and wording.",
                "proposed_revision": "Essential services shall not be cut off or withheld without just and sufficient cause, subject to applicable law. Confirm any proposed enforcement procedure with qualified counsel.",
                "citations": [dict(SOURCES[1])], "applicability": "conditional on supplied facts"})
    return findings
