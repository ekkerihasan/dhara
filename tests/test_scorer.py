from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.tools.law import lookup_section
from env.scorer import score

TASKS = Path(__file__).parents[1] / "env/tasks"


def load(name: str) -> dict:
    return json.loads((TASKS / f"{name}.json").read_text(encoding="utf-8"))


def test_perfect_run_and_wrong_law() -> None:
    task = load("blr_flat")
    perfect = score(task, load("sample_run"))
    assert perfect["total"] == 3
    wrong = score(task, load("sample_run_wronglaw"))
    assert wrong["wrong_law_penalty"] == -1
    assert wrong["total"] == 2


@pytest.mark.parametrize("delta,expected", [(500, 1), (501, 0.8), (600, 0.8), (-500, 1)])
def test_money_tolerance(delta: int, expected: float) -> None:
    run = load("sample_run")
    run["findings"][0]["money_at_risk_inr"] += delta
    assert score(load("blr_flat"), run)["money_within_500"] == expected


def test_missing_and_duplicate_findings_do_not_earn_full_credit() -> None:
    run = load("sample_run")
    run["findings"] = [run["findings"][0]] * 5
    result = score(load("blr_flat"), run)
    assert result["money_within_500"] == 0.2
    assert result["citations_exist"] < 1
    assert score(load("blr_flat"), {"governing_law": "unknown"})["total"] == 0


def test_unknown_and_uncited_claims_fail_citation_check() -> None:
    run = load("sample_run")
    run["claims"] = [{"text": "The law requires it.", "section_id": None},
                     {"text": "Another claim", "section_id": "fake"}]
    assert score(load("blr_flat"), run)["citations_exist"] < 1


def test_rejects_fractional_and_boolean_money() -> None:
    for invalid in (True, 1.5, -1):
        run = load("sample_run")
        run["findings"][0]["money_at_risk_inr"] = invalid
        with pytest.raises(ValidationError):
            score(load("blr_flat"), run)


def test_task_integrity_and_perfect_score_for_every_task() -> None:
    for name in ("blr_flat", "pg_room", "moveout"):
        task = load(name)
        assert task["synthetic"] is True
        run = {"governing_law": task["expected"]["governing_law"], "findings": []}
        for finding in task["expected"]["findings"]:
            assert all(lookup_section(id) for id in finding["expected_sections"])
            assert finding["clause_ref"] in task["agreement_text"]
            actual = deepcopy(finding)
            actual["section_ids"] = actual.pop("expected_sections")
            run["findings"].append(actual)
        assert score(task, run)["total"] == 3
    assert len(load("pg_room")["landlord_pushback"]) == 3
    assert len(load("moveout")["move_in_checklist"]) >= 1
    assert [d["amount_inr"] for d in load("moveout")["claimed_deductions"]] == [15000, 5000, 8000]
