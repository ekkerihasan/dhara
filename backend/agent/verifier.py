"""Fail closed on uncited, unknown and wrong-law legal claims.

This checks citation identity, not whether a section entails a claim. Property
coverage must be established independently before using conditional provisions.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.tools.law import lookup_section

LEGAL = re.compile(r"\b(?:act|section|law|legal|entitled|must|cap|limit)\b|\bs\.", re.IGNORECASE)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    section_id: str | None = None


class Verdict(Claim):
    verdict: Literal["cited", "unverified", "blocked"]
    reason: str


def verify_claims(claims: list[Claim | dict]) -> list[Verdict]:
    """Verify every claim; never silently discard a failed claim."""
    results: list[Verdict] = []
    for value in claims:
        claim = value if isinstance(value, Claim) else Claim.model_validate(value)
        section = lookup_section(claim.section_id) if claim.section_id else None
        if claim.section_id and section is None:
            verdict, reason = "blocked", "Unknown section id"
        elif section and not section["applies_in_karnataka"]:
            verdict, reason = "blocked", "This model provision is not applicable Karnataka law"
        elif section:
            verdict, reason = "cited", "Section exists; claim meaning and property coverage still require review"
        elif LEGAL.search(claim.text):
            verdict, reason = "blocked", "Legal claim requires a known applicable section id"
        else:
            verdict, reason = "unverified", "Non-legal statement; no legal source verified"
        results.append(Verdict(**claim.model_dump(), verdict=verdict, reason=reason))
    return results
