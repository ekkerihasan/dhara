from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_agent import BLR_FINDINGS, scripted_model  # noqa: E402

from backend.llm.provider import ProviderError, ToolCallOrText  # noqa: E402
from env.run_eval import agent_run, baseline_run, evaluate, governing_label, markdown  # noqa: E402

TASK = json.loads((Path(__file__).parents[1] / "env/tasks/blr_flat.json").read_text())


def plain_model(reply: dict):
    def chat(messages, tools) -> ToolCallOrText:
        assert tools == []
        return ToolCallOrText(text="Here is my review:\n" + json.dumps(reply))
    return chat


def test_baseline_counts_every_claim_including_wrong_law() -> None:
    reply = {"governing_law": "KARNATAKA_RENT_ACT",
             "findings": [{"clause_ref": "C2", "category": "deposit_forfeiture", "money_at_risk_inr": 75000, "section_ids": ["MTA-11(1)"]}],
             "claims": [{"text": "The deposit is capped at two months.", "section_id": "MTA-11(1)"}]}
    run = baseline_run(TASK, plain_model(reply))
    assert run["governing_law"] == "KARNATAKA_RENT_ACT"
    assert run["findings"][0]["money_at_risk_inr"] == 75000
    assert len(run["claims"]) == 1


def test_agent_run_scores_only_what_reaches_the_tenant() -> None:
    claims = [{"text": "Karnataka law caps the deposit at two months.", "section_id": "MTA-11(1)"}]
    run = agent_run(TASK, scripted_model(BLR_FINDINGS, claims))
    assert run["governing_law"] == "TPA_CONTRACT"
    assert len(run["findings"]) == 5
    assert all(c["section_id"] != "MTA-11(1)" for c in run["claims"])


def test_agent_coverage_scores_all_five_clauses_when_model_stops_after_three() -> None:
    from env.scorer import score

    run = agent_run(TASK, scripted_model(BLR_FINDINGS[:3], []))
    assert len(run["findings"]) == 5
    assert score(TASK, run)["total"] == 4  # out of 4: the rule fallback also settles the negotiation correctly


def test_unknown_fact_lets_pg_room_finish_unresolved() -> None:
    pg = json.loads((Path(__file__).parents[1] / "env/tasks/pg_room.json").read_text())
    findings = [("C2", "deposit_forfeiture", {"deposit": 16000, "on_any_breach": True, "on_early_exit": True}, ["ICA-74"]),
                ("C3", "painting_or_cleaning_fixed", {"amount": 3000}, ["ICA-74"])]
    run = agent_run(pg, scripted_model(findings, []))
    assert run["status"] == "ready"
    assert run["governing_law"] == "UNRESOLVED"


def test_evaluate_and_markdown() -> None:
    def model(messages, tools):
        if tools:
            return scripted_model(BLR_FINDINGS, [])(messages, tools)
        return plain_model({"governing_law": "TPA_CONTRACT", "findings": [], "claims": []})(messages, tools)

    results = evaluate(model, tasks=("blr_flat",))
    assert {row["mode"] for row in results["rows"]} == {"baseline", "agent"}
    assert "| blr_flat | agent |" in markdown(results, "fake")
    assert "Negotiation correct" in markdown(results, "fake")
    agent = next(row for row in results["rows"] if row["mode"] == "agent")
    assert agent["score"]["negotiation_correct"] == 1.0  # the fake model cannot decide offers: the rule fallback does
    baseline = next(row for row in results["rows"] if row["mode"] == "baseline")
    assert baseline["score"]["negotiation_correct"] == 0.0  # the baseline has no fallback
    assert governing_label(None) == "UNRESOLVED"


def test_provider_fallback_is_not_reported_as_a_successful_live_evaluation() -> None:
    def unavailable(messages, tools):
        raise ProviderError("Model request failed with HTTP 429")

    results = evaluate(unavailable, tasks=("blr_flat",))
    assert results["provider_failures"] == results["model_requests"] == 4  # review and negotiation, baseline and agent
    assert all(row["error"] for row in results["rows"])
    assert "fallback" in results["rows"][1]["error"]


def test_failed_evaluation_preserves_previous_score_artifacts(monkeypatch, tmp_path) -> None:
    import env.run_eval as runner

    (tmp_path / "scores.json").write_text("previous JSON")
    (tmp_path / "scores.md").write_text("previous table")
    monkeypatch.setattr(runner, "RESULTS", tmp_path)
    monkeypatch.setattr(runner, "evaluate", lambda **_: {
        "date": "2026-10-25", "rows": [{"error": "HTTP 429"}],
        "model_requests": 1, "provider_failures": 1})
    import pytest
    with pytest.raises(SystemExit, match="previous scores preserved"):
        runner.main()
    assert (tmp_path / "scores.json").read_text() == "previous JSON"
    assert (tmp_path / "scores.md").read_text() == "previous table"
    assert json.loads((tmp_path / "last_failed_attempt.json").read_text())["provider_failures"] == 1


def test_moveout_agent_run_scores_claimed_deductions() -> None:
    from test_moveout import VERDICTS
    from test_moveout import scripted_model as moveout_model
    from env.run_eval import moveout_run
    from env.scorer import score

    task = json.loads((Path(__file__).parents[1] / "env/tasks/moveout.json").read_text())
    run = moveout_run(task, moveout_model(VERDICTS))
    assert run["governing_law"] == "TPA_CONTRACT"
    assert [f["money_at_risk_inr"] for f in run["findings"]] == [15000, 5000, 8000]
    assert score(task, run)["money_within_500"] == 1.0
