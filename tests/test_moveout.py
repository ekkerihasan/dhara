from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main
from backend.agent.moveout import MoveoutState, next_formal_steps, start_moveout
from backend.llm.provider import ProviderError, ToolCall, ToolCallOrText
from backend.tools.agreement import read_agreement

TASK = json.loads((Path(__file__).parents[1] / "env/tasks/moveout.json").read_text())
DEDUCTIONS = [{"id": f"D{i}", **{k: v for k, v in d.items() if k != "expected_verdict"}} for i, d in enumerate(TASK["claimed_deductions"], start=1)]
CHECKLIST = TASK["move_in_checklist"]

VERDICTS = [
    ("D1", "disputed", ["E1"], ["TPA-108(m)", "KRA-48(5)"]),
    ("D2", "allowed", [], ["ICA-74"]),
    ("D3", "disputed", ["E2"], ["TPA-108(m)"]),
]


def scripted_model(verdicts):
    turns = []

    def chat(messages, tools):
        assert {t["function"]["name"] for t in tools} == {"record_verdict", "finish"}
        turns.append(messages)
        if len(turns) == 1:
            return ToolCallOrText(tool_calls=[ToolCall(id=f"v{i}", name="record_verdict", arguments={
                "deduction_id": d, "verdict": v, "reason": f"{d} reason", "evidence_ids": ev, "section_ids": secs})
                for i, (d, v, ev, secs) in enumerate(verdicts)])
        return ToolCallOrText(tool_calls=[ToolCall(id="f", name="finish", arguments={})])

    chat.turns = turns
    return chat


def state(model) -> MoveoutState:
    return MoveoutState("m1", read_agreement(TASK["agreement_text"])["clauses"], CHECKLIST, [dict(d) for d in DEDUCTIONS], TASK["facts"], "en", model)


def test_model_verdicts_drafts_and_next_steps() -> None:
    model = scripted_model(VERDICTS)
    result = start_moveout(state(model))

    assert result["status"] == "ready"
    assert [(d["id"], d["verdict"]) for d in result["deductions"]] == [("D1", "disputed"), ("D2", "allowed"), ("D3", "disputed")]
    assert result["disputed_inr"] == 15000 + 8000
    assert result["deductions"][0]["section_ids"] == ["TPA-108(m)"]  # the Rent Act does not cover this flat
    assert [d["language"] for d in result["drafts"]] == ["en", "kn"] and all(d["tone"] == "challenge" for d in result["drafts"])
    assert [s["title"] for s in result["next_steps"]][2] == "Civil money-recovery suit"
    assert any(m["role"] == "tool" for m in model.turns[1])


def test_allowed_fixed_cleaning_gets_reasonable_compensation_citation() -> None:
    verdicts = [
        ("D1", "disputed", ["E1"], ["TPA-108(m)"]),
        ("D2", "allowed", [], []),
        ("D3", "disputed", ["E2"], ["TPA-108(m)"]),
    ]
    result = start_moveout(state(scripted_model(verdicts)))

    assert result["deductions"][1]["section_ids"] == ["ICA-74"]


def test_rule_fallback_when_model_unavailable() -> None:
    def down(messages, tools):
        raise ProviderError("offline")

    result = start_moveout(state(down))

    assert [d["verdict"] for d in result["deductions"]] == [t["expected_verdict"] for t in TASK["claimed_deductions"]]
    assert result["deductions"][1]["section_ids"] == ["ICA-74"]
    assert any(s["label"] == "Model unavailable: rule-based fallback" for s in result["trace"])


def test_next_steps_use_rent_controller_only_when_act_applies() -> None:
    assert next_formal_steps(True)[2]["title"] == "Rent Controller"
    assert all("police" not in s["detail"].casefold() for s in next_formal_steps(False))


def test_moveout_api_flow(monkeypatch) -> None:
    monkeypatch.setattr(main, "provider_chat", scripted_model(VERDICTS))
    client = TestClient(main.app)
    body = {"agreement_text": TASK["agreement_text"], "checklist": CHECKLIST,
            "deductions": [{k: v for k, v in d.items() if k != "expected_verdict"} for d in TASK["claimed_deductions"]], "facts": TASK["facts"]}
    review_id = client.post("/api/moveout", json=body).json()["id"]

    ready = client.get(f"/api/moveout/{review_id}").json()
    assert ready["status"] == "ready" and ready["disputed_inr"] == 23000

    approved = client.post(f"/api/moveout/{review_id}/approve", json={"approved": True}).json()
    assert approved["status"] == "approved" and approved["approval"]["delivery_status"] == "not_sent"
    assert client.get("/api/moveout/nope").status_code == 404
