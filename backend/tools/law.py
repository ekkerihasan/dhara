"""Sourced lookup and conservative Karnataka coverage screening.

Current rent is recorded, never substituted for statutory rent. ``applies`` is
None until required facts are confirmed; True remains conditional on those facts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import logging
import math
from pathlib import Path
from typing import Any

from housing.legal import screen_jurisdiction

LOGGER = logging.getLogger(__name__)
LAW_PATH = Path(__file__).resolve().parents[2] / "law" / "karnataka.json"
AREAS = {"municipal_corporation": "part_a", "city_municipal_council": "other_scheduled"}


def lookup_section(id: str) -> dict[str, Any] | None:
    """Return a fresh entry, or None for an unknown citation; never invent one."""
    if not isinstance(id, str):
        raise ValueError("Section id must be text")
    LOGGER.info("lookup_section id=%s", id[:200])
    entries = json.loads(LAW_PATH.read_text(encoding="utf-8"))
    return next((deepcopy(entry) for entry in entries if entry["id"] == id), None)


def _amount(value: float | None, name: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not math.isfinite(value) or value < 0):
        raise ValueError(f"{name} must be a finite non-negative number")


def check_jurisdiction(
    rent_per_month: float | None,
    built_year: int | None,
    local_body: str | None,
    premises_use: str | None,
    substantial_renovation_year: int | None = None,
    *,
    standard_rent_monthly: float | None = None,
    ownership_type: str | None = None,
    other_exemptions_checked: bool | None = None,
    tenancy_date: str | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Wrap the prototype screen and collect all known exclusions.

Year-only dates are deliberately unresolved in the fifteenth anniversary year.
The two supported local-body values encode confirmed First Schedule areas.
Other areas and non-residential/PG premises require separate factual review.
"""
    today = as_of or date.today()
    _amount(rent_per_month, "rent_per_month")
    _amount(standard_rent_monthly, "standard_rent_monthly")
    for name, year in (("built_year", built_year), ("substantial_renovation_year", substantial_renovation_year)):
        if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= today.year):
            raise ValueError(f"{name} must be a past or current calendar year")
    if built_year is not None and substantial_renovation_year is not None and substantial_renovation_year < built_year:
        raise ValueError("Renovation cannot precede construction")
    if tenancy_date is not None:
        try:
            started = date.fromisoformat(tenancy_date)
        except (ValueError, TypeError) as exc:
            raise ValueError("tenancy_date must use YYYY-MM-DD") from exc
        if started > today:
            raise ValueError("tenancy_date cannot be in the future")
    if other_exemptions_checked is not None and not isinstance(other_exemptions_checked, bool):
        raise ValueError("other_exemptions_checked must be true or false")
    for name, value in (("local_body", local_body), ("premises_use", premises_use), ("ownership_type", ownership_type)):
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{name} must be text")

    missing: list[str] = []
    reasons: list[dict[str, str]] = []

    def reason(section_id: str, status: str, text: str) -> None:
        reasons.append({"section_id": section_id, "status": status, "text": text})

    if rent_per_month is None:
        missing.append("rent_per_month")
    area = AREAS.get(local_body or "")
    if area is None:
        missing.append("local_body")
        reason("KRA-2(1)", "needs_input", "Confirm First Schedule coverage; an unknown local body is not an exclusion.")
    if premises_use != "residential":
        missing.append("premises_use")
        reason("KRA-2(3)(g)", "needs_input", "Confirm residential use; PG/lodging and small commercial premises require separate review.")
    if standard_rent_monthly is None:
        missing.append("standard_rent_monthly")
        reason("KRA-2(3)(e)", "needs_input", "Obtain deemed/standard rent; monthly market rent alone does not establish this exclusion.")

    latest_year = max(year for year in (built_year, substantial_renovation_year, 0) if year is not None)
    age = today.year - latest_year if latest_year else None
    if built_year is None:
        missing.append("built_year")
    if age == 15:
        missing.append("completion_date")
        reason("KRA-2(3)(f)", "needs_input", "Confirm the exact completion date at the fifteen-year boundary.")

    facts = {
        "city": "Confirmed scheduled area" if area else "",
        "schedule_area": area or "unknown",
        "monthly_rent": rent_per_month,
        "standard_rent_monthly": standard_rent_monthly,
        "building_age_years": None if age == 15 else age,
        "residential": premises_use == "residential",
        "ownership_type": ownership_type or "unknown",
        "other_exemptions_checked": other_exemptions_checked,
        "tenancy_date": tenancy_date,
    }
    screened = screen_jurisdiction("Karnataka", facts)
    # The prototype short-circuits on the first exclusion. Reuse it with each
    # independent factor isolated so the trace explains every known exclusion.
    for section_id, overrides in (
        ("KRA-2(3)(e)", {"ownership_type": "unknown", "building_age_years": None}),
        ("KRA-2(3)(f)", {"ownership_type": "unknown", "standard_rent_monthly": None}),
        ("KRA-2(3)(a)", {"building_age_years": None, "standard_rent_monthly": None}),
    ):
        result = screen_jurisdiction("Karnataka", {**facts, **overrides})
        if result["status"] == "rent_act_excluded":
            if section_id == "KRA-2(3)(a)" and ownership_type == "cooperative":
                section_id = "KRA-2(3)(b)"
            # Market committee and government-grant exclusions are not in this
            # compact library; keep their legal conclusion unverified.
            if section_id == "KRA-2(3)(a)" and ownership_type in {"market_committee", "government_grant"}:
                section_id = "unverified"
            reason(section_id, "excluded", result["reasons"][0])

    if ownership_type not in {"private", "government", "religious_charitable", "wakf", "cooperative", "market_committee", "government_grant"}:
        missing.append("ownership_type")
    if other_exemptions_checked is not True:
        missing.append("other_exemptions_checked")
    if not tenancy_date or tenancy_date < "2001-12-31":
        missing.append("tenancy_date")
    excluded = screened["status"] == "rent_act_excluded"
    applies = False if excluded else True if not missing and screened["conditional_rules_enabled"] else None
    if applies is True:
        reason("KRA-2(1)", "conditional", "No encoded exclusion found; coverage is conditional on supplied facts and notifications.")
    LOGGER.info("check_jurisdiction inputs=%s", str({"rent": rent_per_month, "built": built_year, "body": local_body, "use": premises_use})[:200])
    return {"applies": applies, "reasons": reasons, "missing": list(dict.fromkeys(missing)),
            "note": screened["note"], "questions": screened["questions"]}
