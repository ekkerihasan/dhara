from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_agent import BLR_FINDINGS, scripted_model  # noqa: E402

import backend.main as main  # noqa: E402

TASK = json.loads((Path(__file__).parents[1] / "env/tasks/blr_flat.json").read_text())


@pytest.fixture()
def client(monkeypatch):
    claims = [{"text": "Karnataka law caps the deposit at two months.", "section_id": "MTA-11(1)"}]
    monkeypatch.setattr(main, "provider_chat", scripted_model(BLR_FINDINGS, claims))
    main.RUNS.clear()
    return TestClient(main.app)


def test_full_flow_question_answer_approve(client) -> None:
    facts = {"rent_per_month": 25000, "local_body": "municipal_corporation", "premises_use": "residential"}
    created = client.post("/api/runs", json={"agreement_text": TASK["agreement_text"], "facts": facts, "language": "en"})
    assert created.status_code == 200
    run_id = created.json()["id"]

    paused = client.get(f"/api/runs/{run_id}").json()
    assert paused["status"] == "needs_input"
    assert paused["question"] == "Please provide the missing tenancy fact(s): built_year."
    assert paused["trace"][0]["data"]["tool"] == "read_agreement"

    assert client.post(f"/api/runs/{run_id}/answer", json={"facts": {"built_year": 2019}}).status_code == 200
    ready = client.get(f"/api/runs/{run_id}").json()
    assert ready["status"] == "ready"
    assert len(ready["findings"]) == 5
    assert [d["language"] for d in ready["drafts"]] == ["en", "kn", "hi"]
    assert any(v["verdict"] == "blocked" and v["section_id"] == "MTA-11(1)" for v in ready["verdicts"])

    approved = client.post(f"/api/runs/{run_id}/approve", json={"approved": True}).json()
    assert approved["status"] == "approved"
    assert approved["approval"]["delivery_status"] == "not_sent"


def test_pdf_upload_is_read_in_memory(client) -> None:
    pdf = base64.b64encode(b"not a pdf").decode()
    response = client.post("/api/runs", json={"pdf_base64": pdf, "facts": TASK["facts"]})
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_errors(client) -> None:
    assert client.post("/api/runs", json={"facts": TASK["facts"]}).status_code == 400
    assert client.get("/api/runs/nope").status_code == 404
    run_id = client.post("/api/runs", json={"agreement_text": TASK["agreement_text"], "facts": TASK["facts"]}).json()["id"]
    assert client.post(f"/api/runs/{run_id}/approve", json={"approved": False}).status_code == 400
    assert client.post(f"/api/runs/{run_id}/answer", json={"facts": {"built_year": 2019}}).status_code == 409
    assert client.post("/api/runs", json={"agreement_text": "x", "facts": {"deposit_inr": 1}}).status_code == 422


def test_cors_allows_the_frontend(client) -> None:
    response = client.options("/api/runs", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_answer_lets_the_run_continue_unresolved(client) -> None:
    facts = {"rent_per_month": 8000, "local_body": "municipal_corporation", "premises_use": "residential"}
    run_id = client.post("/api/runs", json={"agreement_text": TASK["agreement_text"], "facts": facts}).json()["id"]
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "needs_input"

    client.post(f"/api/runs/{run_id}/answer", json={"facts": {"built_year": None}})
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "ready"
    checks = [s["data"] for s in run["trace"] if s["data"].get("tool") == "check_jurisdiction" and "output" in s["data"]]
    jurisdiction = checks[-1]["output"]
    assert jurisdiction["applies"] is None
