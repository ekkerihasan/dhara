"""Score structured runs without a model. Perfect score is 3, or 4 on tasks with a scripted landlord; penalties unbounded."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.agent.landlord import is_acceptable
from backend.tools.law import lookup_section


class Finding(BaseModel):
    model_config = ConfigDict(extra="allow")
    clause_ref: str
    category: str
    money_at_risk_inr: StrictInt = Field(ge=0)
    section_ids: list[str] = Field(default_factory=list)


class Run(BaseModel):
    model_config = ConfigDict(extra="allow")
    governing_law: str
    findings: list[Finding] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    negotiation: dict[str, Any] | None = None


def negotiation_correct(task: dict[str, Any], negotiation: dict[str, Any] | None) -> float | None:
    """Over every landlord offer in every round: did the tenant accept exactly the acceptable ones?

A counter counts as not accepting. An offer left without a decision counts as wrong.
None when the task has no scripted landlord.
"""
    if not task.get("landlord_moves"):
        return None
    results: list[bool] = []
    for played in (negotiation or {}).get("rounds", []):
        decisions = {d["clause_id"]: d["decision"] for d in played.get("decisions", [])}
        for offer in played.get("offers", []):
            acceptable = is_acceptable(offer["move_id"], task)
            decision = decisions.get(offer["clause_id"])
            results.append(acceptable is not None and decision is not None and (decision == "accept") == acceptable)
    return sum(results) / len(results) if results else 0.0


def score(task: dict[str, Any], run: dict[str, Any] | Run) -> dict[str, int | float]:
    """Match each expected clause/category once; missing results cannot earn credit.

Citation existence is an identity check, not a claim-entailment judgment. Wrong
law is penalised for each emitted reference, including references in claims.
"""
    parsed = run if isinstance(run, Run) else Run.model_validate(run)
    expected = task["expected"]
    findings = expected["findings"]
    consumed: set[int] = set()
    correct_money = 0
    citations: list[str | None] = []
    for target in findings:
        match = next((i for i, actual in enumerate(parsed.findings)
                      if i not in consumed and actual.clause_ref == target["clause_ref"]
                      and actual.category == target["category"]), None)
        if match is not None:
            consumed.add(match)
            actual = parsed.findings[match]
            correct_money += abs(actual.money_at_risk_inr - target["money_at_risk_inr"]) <= 500
            if target["expected_sections"] and not actual.section_ids:
                citations.append(None)
        elif target["expected_sections"]:
            citations.append(None)
    for finding in parsed.findings:
        citations.extend(finding.section_ids)
    for claim in parsed.claims:
        # Explicit uncited legal claims are included as failed citation checks.
        if claim.get("section_id") is not None:
            citations.append(claim["section_id"])
        else:
            from backend.agent.verifier import LEGAL
            if LEGAL.search(str(claim.get("text", ""))):
                citations.append(None)
    if any(ref is not None and not isinstance(ref, str) for ref in citations):
        raise ValueError("Citation ids must be strings")
    governing = int(parsed.governing_law == expected["governing_law"])
    money = correct_money / len(findings) if findings else 0.0
    existing = sum(lookup_section(ref) is not None for ref in citations if ref)
    citation_fraction = existing / len(citations) if citations else 0.0
    forbidden = set(expected["forbidden_sections"])
    penalty = -sum(ref in forbidden for ref in citations)
    negotiation = negotiation_correct(task, parsed.negotiation)
    return {"governing_law_correct": governing, "money_within_500": money,
            "citations_exist": citation_fraction, "negotiation_correct": negotiation, "wrong_law_penalty": penalty,
            "total": governing + money + citation_fraction + (negotiation or 0.0) + penalty}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m env.scorer TASK.json RUN.json")
    task, run = (json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:])
    result = score(task, run)
    print("| Check | Score |\n| --- | ---: |")
    for name, value in result.items():
        print(f"| {name} | {'n/a' if value is None else format(value, 'g')} |")


if __name__ == "__main__":
    main()
