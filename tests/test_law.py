from datetime import date

import pytest

from backend.tools.law import check_jurisdiction, lookup_section

TODAY = date(2026, 10, 24)


def screen(**overrides: object) -> dict:
    facts = dict(rent_per_month=3000, built_year=1990, local_body="municipal_corporation",
                 premises_use="residential", standard_rent_monthly=3000,
                 ownership_type="private", other_exemptions_checked=True,
                 tenancy_date="2026-10-01", as_of=TODAY)
    return check_jurisdiction(**{**facts, **overrides})


def test_modern_flat_reports_both_exclusions_when_statutory_rent_confirmed() -> None:
    result = screen(rent_per_month=25000, standard_rent_monthly=25000, built_year=2019)
    assert result["applies"] is False
    assert {r["section_id"] for r in result["reasons"] if r["status"] == "excluded"} == {"KRA-2(3)(e)", "KRA-2(3)(f)"}


def test_current_rent_does_not_establish_statutory_exclusion() -> None:
    result = screen(rent_per_month=25000, standard_rent_monthly=None)
    assert result["applies"] is None
    assert "standard_rent_monthly" in result["missing"]
    result = screen(rent_per_month=25000, built_year=2019, standard_rent_monthly=None)
    assert result["applies"] is False
    assert {r["section_id"] for r in result["reasons"]} == {"KRA-2(3)(e)", "KRA-2(3)(f)"}


def test_old_building_and_council_threshold() -> None:
    assert screen()["applies"] is True
    assert screen(local_body="city_municipal_council")["applies"] is False
    assert screen(local_body="city_municipal_council", standard_rent_monthly=2000)["applies"] is True
    assert screen(standard_rent_monthly=3500)["applies"] is True
    assert screen(standard_rent_monthly=3501)["applies"] is False


@pytest.mark.parametrize("field", ["built_year", "local_body", "premises_use", "ownership_type", "other_exemptions_checked", "tenancy_date"])
def test_missing_inputs_pause_coverage(field: str) -> None:
    result = screen(**{field: None})
    assert result["applies"] is None
    assert field in result["missing"]


def test_model_act_is_explicitly_inapplicable_and_lookup_is_isolated() -> None:
    for id in ("MTA-11(1)", "MTA-30"):
        assert lookup_section(id)["applies_in_karnataka"] is False
    entry = lookup_section("KRA-49")
    entry["paraphrase"] = "changed"
    assert lookup_section("KRA-49")["paraphrase"] != "changed"
    assert lookup_section("invented") is None


def test_renovation_age_and_year_boundary() -> None:
    assert screen(substantial_renovation_year=2020)["applies"] is False
    result = screen(built_year=2011)
    assert result["applies"] is None
    assert "completion_month" in result["missing"]


def test_completion_month_settles_the_fifteen_year_boundary() -> None:
    # TODAY is 24 Oct 2026, so a 2011 building turns 15 this year.
    under = screen(built_year=2011, completion_month=11)
    assert under["applies"] is False
    assert any(r["section_id"] == "KRA-2(3)(f)" and r["status"] == "excluded" for r in under["reasons"])
    over = screen(built_year=2011, completion_month=3)
    assert "completion_month" not in over["missing"]
    assert not any(r["section_id"] == "KRA-2(3)(f)" for r in over["reasons"])
    same = screen(built_year=2011, completion_month=10)
    assert same["applies"] is None and "completion_date" in same["missing"]


@pytest.mark.parametrize("overrides", [
    {"rent_per_month": -1}, {"standard_rent_monthly": float("nan")},
    {"built_year": True}, {"built_year": 2027},
    {"substantial_renovation_year": 1980}, {"other_exemptions_checked": "yes"},
    {"tenancy_date": "tomorrow"}, {"local_body": []},
    {"completion_month": 13}, {"completion_month": True},
])
def test_invalid_inputs(overrides: dict) -> None:
    with pytest.raises(ValueError):
        screen(**overrides)


def test_non_residential_or_unknown_area_needs_review() -> None:
    assert screen(premises_use="commercial")["applies"] is None
    assert screen(premises_use="pg")["applies"] is None
    assert screen(local_body="town_panchayat")["applies"] is None
