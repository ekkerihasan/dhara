from __future__ import annotations

import json
from pathlib import Path

from backend.agent.tenant import AgentState, start_agent
from backend.llm.provider import ToolCallOrText
from backend.tools.agreement import read_agreement


TASK = json.loads((Path(__file__).parents[1] / "env/tasks/blr_flat.json").read_text())


def fake_provider(messages, tools) -> ToolCallOrText:
    assert tools
    assert "150000" in messages[-1]["content"]
    return ToolCallOrText(text=None, tool_calls=[])


def test_agent_runs_tools_verifies_and_drafts_without_network() -> None:
    state = AgentState("run-1", read_agreement(TASK["agreement_text"])["clauses"], TASK["facts"], "en", fake_provider)

    result = start_agent(state)

    assert result.status == "ready"
    assert len(result.findings) == 5
    assert {step.type for step in result.trace} >= {"plan", "tool_call", "verifier", "draft"}
    assert all(verdict["verdict"] in {"cited", "unverified"} for verdict in result.verdicts)
    assert result.drafts[0].language == "en"


def test_agent_pauses_then_resumes_when_built_year_arrives() -> None:
    facts = {"rent_per_month": 25000, "local_body": "municipal_corporation", "premises_use": "residential"}
    state = AgentState("run-2", read_agreement(TASK["agreement_text"])["clauses"], facts, "en", fake_provider)

    paused = start_agent(state)
    assert paused.status == "needs_input"
    assert paused.question
    assert "built_year" in paused.question

    state.facts["built_year"] = 2019
    resumed = start_agent(state)
    assert resumed.status == "ready"
    assert resumed.drafts
    assert any(step.type == "question" for step in resumed.trace)
