from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

import backend.main as main
from backend.llm.provider import ProviderError, ToolCallOrText


def test_api_baseline_has_no_tools_verifies_claims_and_never_creates_actionable_drafts(monkeypatch):
    captured = []

    def model(messages, tools):
        assert tools == []
        captured.append(json.dumps(messages))
        return ToolCallOrText(text=json.dumps({"governing_law": "KARNATAKA_RENT_ACT", "findings": [
            {"clause_ref": "C2", "category": "deposit_forfeiture", "money_at_risk_inr": 50000,
             "section_ids": ["MTA-11(1)"]}], "claims": [
            {"text": "The law caps deposits at two months.", "section_id": "MTA-11(1)"},
            {"text": "Section 74 addresses reasonable compensation.", "section_id": "ICA-74"},
            {"text": "The Act gives this tenancy a rent receipt entitlement.", "section_id": "KRA-16"}]}))

    monkeypatch.setattr(main, "provider_chat", model)
    client = TestClient(main.app)
    created = client.post("/api/runs?mode=baseline", json={"agreement_text": "C1. My PAN is ABCDE1234F; phone 9876543210.", "facts": {}})
    assert created.status_code == 200
    path = f"/api/runs/{created.json()['id']}"
    result = client.get(path).json()
    assert result["mode"] == "baseline" and result["status"] == "ready"
    assert result["findings"] == [] and result["drafts"] == []
    assert result["baseline_output"]["findings"][0]["section_ids"] == ["MTA-11(1)"]
    assert result["baseline_output"]["verified"] is False
    assert result["baseline_output"]["actionable"] is False
    assert [v["verdict"] for v in result["verdicts"]] == ["blocked", "cited", "blocked"]
    assert "ABCDE1234F" not in captured[0] and "9876543210" not in captured[0]
    assert client.post(path + "/approve", json={"approved": True}).status_code == 409
    assert client.post("/api/runs?mode=unknown", json={"agreement_text": "Sample"}).status_code == 422


@pytest.mark.parametrize("reply", ["not JSON", "[]", '{"findings": {}}', "``` ```"])
def test_malformed_baseline_fails_without_silently_running_agent(monkeypatch, reply):
    monkeypatch.setattr(main, "provider_chat", lambda messages, tools: ToolCallOrText(text=reply))
    client = TestClient(main.app)
    run_id = client.post("/api/runs?mode=baseline", json={"agreement_text": "C1. Sample."}).json()["id"]
    result = client.get(f"/api/runs/{run_id}").json()
    assert result["status"] == "failed"
    assert result["baseline_output"] is None and result["drafts"] == []


def test_provider_failure_does_not_leak_error_or_fallback(monkeypatch):
    def down(messages, tools):
        raise ProviderError("private provider details")

    monkeypatch.setattr(main, "provider_chat", down)
    client = TestClient(main.app)
    run_id = client.post("/api/runs?mode=baseline", json={"agreement_text": "Sample"}).json()["id"]
    result = client.get(f"/api/runs/{run_id}")
    assert result.json()["status"] == "failed" and "private provider details" not in result.text
