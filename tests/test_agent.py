from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agent.tenant import AgentState, start_agent
from backend.llm.provider import ProviderError, ToolCall, ToolCallOrText
from backend.tools.agreement import read_agreement


TASK = json.loads((Path(__file__).parents[1] / "env/tasks/blr_flat.json").read_text())

# What a model reading the blr_flat clauses would propose. Amounts are never in here: compute_money sets them.
BLR_FINDINGS = [
    ("C2", "deposit_forfeiture", {"deposit": 150000, "on_any_breach": True, "on_early_exit": True}, ["ICA-74"]),
    ("C3", "lock_in", {"monthly_rent": 25000, "remaining_months": 6}, ["ICA-74"]),
    ("C4", "painting_or_cleaning_fixed", {"amount": 15000}, ["TPA-108(m)", "ICA-74"]),
    ("C5", "rent_escalation_excess", {"monthly_rent": 25000, "escalation_percent": 15}, []),
    ("C6", "notice_shortfall", {"monthly_rent": 25000, "required_months": 2, "given_months": 1}, ["TPA-106"]),
]


def scripted_model(findings, claims):
    """A fake model: records findings on its first turn, then calls finish. Records every message it sees."""
    seen: list[list[dict]] = []

    def chat(messages, tools) -> ToolCallOrText:
        assert {tool["function"]["name"] for tool in tools} == {"record_finding", "lookup_section", "finish"}
        seen.append([dict(message) for message in messages])
        if len(seen) == 1:
            calls = [ToolCall(id=f"call_{i}", name="record_finding", arguments={
                "clause_ref": ref, "category": category, "inputs": inputs, "section_ids": sections,
                "issue": f"{ref} is unfair to the tenant.", "ask": f"Revise {ref}."}) for i, (ref, category, inputs, sections) in enumerate(findings)]
            return ToolCallOrText(tool_calls=calls)
        return ToolCallOrText(tool_calls=[ToolCall(id="call_finish", name="finish", arguments={"claims": claims})])

    chat.seen = seen
    return chat


def unavailable_model(messages, tools) -> ToolCallOrText:
    raise ProviderError("No API key configured for groq")


def test_model_drives_findings_and_sees_each_tool_result() -> None:
    model = scripted_model(BLR_FINDINGS, [{"text": "Karnataka law caps the deposit at two months.", "section_id": "MTA-11(1)"}])
    state = AgentState("run-1", read_agreement(TASK["agreement_text"])["clauses"], TASK["facts"], "en", model)

    result = start_agent(state)

    assert result.status == "ready"
    assert [(f.clause_ref, f.money_at_risk_inr) for f in result.findings] == [
        ("C2", 150000), ("C3", 150000), ("C4", 15000), ("C5", 15000), ("C6", 25000)]
    second_turn = model.seen[1]
    tool_results = [m for m in second_turn if m["role"] == "tool"]
    assert len(tool_results) == 5 and '"money_at_risk_inr": 150000' in tool_results[0]["content"]
    assert any(v["verdict"] == "blocked" and v["section_id"] == "MTA-11(1)" for v in result.verdicts)
    assert [d.language for d in result.drafts] == ["en", "kn"]
    assert result.findings[0].clause_text.startswith("C2.")


def test_model_cannot_cite_inapplicable_sections_on_a_finding() -> None:
    findings = [("C2", "deposit_forfeiture", {"deposit": 150000, "on_any_breach": True}, ["ICA-74", "MTA-11(1)", "XYZ-1"])]
    state = AgentState("run-2", read_agreement(TASK["agreement_text"])["clauses"], TASK["facts"], "en", scripted_model(findings, []))

    result = start_agent(state)

    assert result.findings[0].section_ids == ["ICA-74"]


def test_differently_worded_agreement_still_gets_findings() -> None:
    text = ("C1. The monthly rent is Rs 25,000.\n"
            "C2. If the Tenant vacates before the lock-in period, the entire security deposit of Rs 2,50,000 shall stand forfeited.")
    findings = [("C2", "deposit_forfeiture", {"deposit": 250000, "on_early_exit": True}, ["ICA-74"])]
    state = AgentState("run-3", read_agreement(text)["clauses"], TASK["facts"], "en", scripted_model(findings, []))

    result = start_agent(state)

    assert [(f.clause_ref, f.money_at_risk_inr) for f in result.findings] == [("C2", 250000)]


def test_rule_based_fallback_when_model_is_unavailable() -> None:
    state = AgentState("run-4", read_agreement(TASK["agreement_text"])["clauses"], TASK["facts"], "en", unavailable_model)

    result = start_agent(state)

    assert result.status == "ready"
    assert len(result.findings) == 5
    assert all(f.clause_text and f.ask for f in result.findings)
    assert any(step.label == "Model unavailable: rule-based fallback" for step in result.trace)


def test_coverage_check_recovers_clauses_omitted_by_successful_model() -> None:
    model = scripted_model(BLR_FINDINGS[:3], [])
    state = AgentState("partial", read_agreement(TASK["agreement_text"])["clauses"], TASK["facts"], "en", model)

    result = start_agent(state)

    assert result.status == "ready"
    assert [(f.clause_ref, f.money_at_risk_inr) for f in result.findings] == [
        ("C2", 150000), ("C3", 150000), ("C4", 15000), ("C5", 15000), ("C6", 25000)]
    assert result.findings[3].model_extra["source"] == "rule_based_coverage"
    assert result.findings[0].issue == "C2 is unfair to the tenant."
    assert result.findings[3].section_ids == []
    assert "product" in result.findings[3].issue
    assert any(step.label == "Rule-based coverage check" for step in result.trace)
    assert not any("Model unavailable" in step.label for step in result.trace)
    assert state.tool_calls <= 12


def test_coverage_check_does_not_invent_charges_for_an_unpriced_clause() -> None:
    text = "C1. Monthly rent is INR 25000.\nC2. Painting costs will be discussed after inspection."
    state = AgentState("unpriced", read_agreement(text)["clauses"], TASK["facts"], "en", scripted_model([], []))
    assert start_agent(state).findings == []


@pytest.mark.parametrize("clause", [
    "The full deposit is not forfeited for any breach or early exit.",
    "There is no deposit forfeiture for early exit.",
    "The deposit is returned after inspection on early exit.",
    "Rent is INR 25000; painting costs will be discussed after inspection.",
    "Monthly escalation is 15 percent.",
    "Two months' notice is required; three month has been given.",
])
def test_coverage_check_requires_an_explicit_adverse_priced_term(clause) -> None:
    text = f"C1. Monthly rent is INR 25000 and the security deposit is INR 150000.\nC2. {clause}"
    state = AgentState("noncharge", read_agreement(text)["clauses"], TASK["facts"], "en", scripted_model([], []))
    result = start_agent(state)
    assert result.status == "ready"
    assert result.findings == []


def test_invalid_coverage_number_does_not_discard_model_findings() -> None:
    text = TASK["agreement_text"] + "\nC7. Annual escalation is 1.2.3 percent.\nC8. A fixed cleaning charge of INR 9999999999999999999 is deducted on exit."
    model = scripted_model(BLR_FINDINGS[:3], [])
    state = AgentState("invalid-number", read_agreement(text)["clauses"], TASK["facts"], "en", model)
    result = start_agent(state)
    assert result.status == "ready"
    assert len(result.findings) == 5
    assert all(f.clause_ref not in {"C7", "C8"} for f in result.findings)


def test_agent_pauses_for_built_year_only_then_resumes() -> None:
    facts = {"rent_per_month": 25000, "local_body": "municipal_corporation", "premises_use": "residential"}
    state = AgentState("run-5", read_agreement(TASK["agreement_text"])["clauses"], facts, "en", scripted_model(BLR_FINDINGS, []))

    paused = start_agent(state)
    assert paused.status == "needs_input"
    assert paused.question == "Please provide the missing tenancy fact(s): built_year."

    state.facts["built_year"] = 2019
    resumed = start_agent(state)
    assert resumed.status == "ready"
    assert resumed.drafts
    assert any(step.type == "question" for step in resumed.trace)
