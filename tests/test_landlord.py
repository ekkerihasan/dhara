"""Model-driven negotiation without network, including API approval and failure gates."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

import backend.main as main
from backend.agent.landlord import (NegotiationMessage, NegotiationRequest, advance_landlord,
    new_negotiation, prepare_message)
from backend.llm.provider import ProviderError, ToolCall, ToolCallOrText


def model_response(decision="counter", statements=None):
    return ToolCallOrText(tool_calls=[ToolCall(id="landlord", name="respond_to_tenant", arguments={
        "decision": decision, "statements": statements or [
            {"text": "I propose a documented cleaning charge rather than an automatic deduction.", "section_id": None},
            {"text": "Section 74 addresses reasonable compensation for stipulated sums.", "section_id": "ICA-74"}]} )])


def state(model):
    return new_negotiation("n1", NegotiationRequest(task_id="pg_room", approved=True,
        tenant_message="Please replace blanket forfeiture with documented reasonable loss."), model)


def test_model_uses_pg_agreement_and_real_tenant_history():
    calls = []

    def model(messages, tools):
        calls.append(messages)
        assert tools[0]["function"]["name"] == "respond_to_tenant"
        return model_response("counter" if len(calls) == 1 else "accept")

    negotiation = state(model)
    first = advance_landlord(negotiation)
    assert first.status == "ready" and first.rounds_remaining == 2
    assert first.turns[0]["source"] == "model"
    assert first.turns[0]["statements"][1]["verdict"] == "cited"
    assert "16000" in json.dumps(calls[0])
    assert "Cleaning costs are fixed; I will not show receipts." not in json.dumps(calls[0])
    prepare_message(negotiation, NegotiationMessage(approved=True, tenant_message="Agreed, please document costs."))
    second = advance_landlord(negotiation)
    assert second.status == "accepted"
    assert calls[1][-2]["role"] == "assistant"
    assert calls[1][-1]["content"] == "Agreed, please document costs."
    assert second.delivery_status == "not_sent" and second.simulated and second.not_a_lawyer
    with pytest.raises(ValueError, match="finished"):
        prepare_message(negotiation, NegotiationMessage(approved=True, tenant_message="A third offer"))


@pytest.mark.parametrize("section,text", [
    ("MTA-11(1)", "The law caps deposits at two months."),
    (None, "The law requires automatic forfeiture."),
    ("FAKE-99", "This section permits forfeiture."),
    ("KRA-49", "The Act prohibits cutting supplies."),
])
def test_bad_legal_claims_fail_closed(section, text):
    negotiation = state(lambda messages, tools: model_response(statements=[{"text": text, "section_id": section}]))
    result = advance_landlord(negotiation)
    assert result.status == "failed" and not result.turns
    assert any(step.type == "verifier" and step.data["verdict"] == "blocked" for step in result.trace)


def test_provider_failure_is_not_presented_as_scripted_landlord():
    def down(messages, tools):
        raise ProviderError("sensitive failure details")

    result = advance_landlord(state(down))
    assert result.status == "failed" and not result.turns
    assert "sensitive" not in result.model_dump_json()


@pytest.mark.parametrize("text", [
    "Section 74 of the Indian Contract Act addresses reasonable compensation.",
    "Deposit deductions reflect documented reasonable loss in accordance with ICA‑74.",
])
def test_one_verifier_feedback_correction_preserves_tool_transcript(text):
    calls = []

    def model(messages, tools):
        calls.append(list(messages))
        if len(calls) == 1:
            return model_response(statements=[{"text": text, "section_id": None}])
        assert messages[-2]["role"] == "assistant"
        assert messages[-2]["tool_calls"][0]["id"] == "landlord"
        assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "landlord"
        feedback = json.loads(messages[-1]["content"])
        assert feedback["accepted"] is False and feedback["verdicts"][0]["verdict"] == "blocked"
        return model_response(statements=[{"text": text, "section_id": "ICA-74"}])

    result = advance_landlord(state(model))
    assert result.status == "ready" and len(result.turns) == 1 and len(calls) == 2
    assert result.turns[0]["statements"][0]["verdict"] == "cited"
    assert [step.data["verdict"] for step in result.trace if step.type == "verifier"] == ["blocked", "cited"]


def test_verifier_correction_is_bounded_to_two_model_calls():
    calls = []

    def model(messages, tools):
        calls.append(list(messages))
        return model_response(statements=[{"text": "The law caps deposits at two months.", "section_id": "MTA-11(1)"}])

    result = advance_landlord(state(model))
    assert result.status == "failed" and not result.turns and len(calls) == 2


@pytest.mark.parametrize("response", [
    ToolCallOrText(text="An unstructured claim that bypasses the verifier."),
    ToolCallOrText(tool_calls=[ToolCall(id="x", name="respond_to_tenant", arguments={
        "decision": "accept", "statements": []})]),
    ToolCallOrText(tool_calls=[ToolCall(id="x", name="unknown_tool", arguments={})]),
])
def test_malformed_responses_never_become_landlord_turns(response):
    result = advance_landlord(state(lambda messages, tools: response))
    assert result.status == "failed" and not result.turns


def test_redacts_both_sides_before_model_and_response():
    captured = []

    def model(messages, tools):
        captured.append(json.dumps(messages))
        return model_response(statements=[{"text": "Call 9876543210 about the proposal.", "section_id": None}])

    request = NegotiationRequest(agreement_text="C1. Phone 9876543210. Deposit INR 16000.",
        tenant_message="My PAN ABCDE1234F and Aadhaar 1234 5678 9012.", approved=True)
    negotiation = new_negotiation("n2", request, model)
    result = advance_landlord(negotiation)
    assert result.status == "ready"
    for sensitive in ("9876543210", "ABCDE1234F", "1234 5678 9012"):
        assert sensitive not in captured[0]
        assert sensitive not in result.model_dump_json()


def test_three_round_limit_duplicate_and_per_offer_approval():
    negotiation = state(lambda messages, tools: model_response())
    advance_landlord(negotiation)
    with pytest.raises(ValueError, match="approval"):
        prepare_message(negotiation, NegotiationMessage(tenant_message="Another offer"))
    with pytest.raises(ValueError, match="already been"):
        prepare_message(negotiation, NegotiationMessage(tenant_message=negotiation.turns[0]["tenant_message"], approved=True))
    for message in ("Please cap cleaning at evidenced cost.", "Please revise the final wording."):
        prepare_message(negotiation, NegotiationMessage(tenant_message=message, approved=True))
        advance_landlord(negotiation)
    assert negotiation.response().status == "exhausted"
    assert negotiation.response().rounds_remaining == 0
    with pytest.raises(ValueError):
        prepare_message(negotiation, NegotiationMessage(tenant_message="One more", approved=True))


def test_landlord_api_sample_approval_and_followup(monkeypatch):
    monkeypatch.setattr(main, "provider_chat", lambda messages, tools: model_response())
    client = TestClient(main.app)
    body = {"task_id": "pg_room", "tenant_message": "Please revise forfeiture and cleaning."}
    assert client.post("/api/negotiations", json=body).status_code == 400
    created = client.post("/api/negotiations", json={**body, "approved": True})
    assert created.status_code == 200
    path = f"/api/negotiations/{created.json()['id']}"
    ready = client.get(path).json()
    assert ready["status"] == "ready" and len(ready["turns"]) == 1
    assert client.post(path + "/message", json={"tenant_message": "What about receipts?"}).status_code == 400
    assert client.post(path + "/message", json={"tenant_message": "What about receipts?", "approved": True}).status_code == 200
    assert len(client.get(path).json()["turns"]) == 2
    assert client.get("/api/negotiations/unknown").status_code == 404
    assert client.post("/api/negotiations", json={**body, "agreement_text": "Also text"}).status_code == 422
