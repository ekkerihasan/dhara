from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_agent import BLR_FINDINGS, scripted_model  # noqa: E402

import backend.main as main  # noqa: E402
from backend.agent import scripted_landlord as landlord  # noqa: E402
from backend.agent.negotiation import FALLBACK_REASON, negotiate  # noqa: E402
from backend.agent.tenant import AgentState  # noqa: E402
from backend.llm.provider import ProviderError, ToolCall, ToolCallOrText  # noqa: E402
from backend.models import Decision, TenantLimits  # noqa: E402
from backend.tools.agreement import read_agreement  # noqa: E402
from env.scorer import negotiation_correct  # noqa: E402

TASKS = Path(__file__).parents[1] / "env/tasks"
BLR = json.loads((TASKS / "blr_flat.json").read_text(encoding="utf-8"))
PG = json.loads((TASKS / "pg_room.json").read_text(encoding="utf-8"))
FINDINGS = [{"clause_ref": "C2", "category": "deposit_forfeiture", "ask": "Replace forfeiture.", "section_ids": ["ICA-74"]},
            {"clause_ref": "C3", "category": "lock_in", "ask": "Cap the lock-in.", "section_ids": ["ICA-74"]},
            {"clause_ref": "C4", "category": "painting_or_cleaning_fixed", "ask": "Charge only for damage.", "section_ids": ["TPA-108(m)"]},
            {"clause_ref": "C6", "category": "notice_shortfall", "ask": "Count the notice given.", "section_ids": ["TPA-106"]}]


def decide_model(rule):
    """A fake model that answers every offer it is shown with rule(offer) -> (decision, section_id)."""
    calls: list[list[dict]] = []

    def chat(messages, tools) -> ToolCallOrText:
        assert [t["function"]["name"] for t in tools] == ["decide_offers"]
        calls.append(messages)
        offers = json.loads(messages[1]["content"])["offers"]
        decisions = [{"clause_id": o["clause_id"], "decision": rule(o)[0], "section_id": rule(o)[1],
                      "reason": f"{o['clause_id']} decided", "counter_terms": None} for o in offers]
        return ToolCallOrText(tool_calls=[ToolCall(id="d", name="decide_offers", arguments={"decisions": decisions})])

    chat.calls = calls
    return chat


def state_for(task: dict, model, persona: str = "strict_owner") -> AgentState:
    state = AgentState(task["id"], read_agreement(task["agreement_text"])["clauses"], dict(task["facts"]), "en", model)
    state.persona = persona
    return state


def test_landlord_moves_are_deterministic_and_match_the_rules() -> None:
    for task in (BLR, PG):
        ids = list(task["landlord_moves"])
        for persona in ("strict_owner", "reasonable_broker"):
            first = landlord.opening(task, persona, ids)
            assert first == landlord.opening(task, persona, ids)
            assert [o.clause_id for o in first] == ids
            assert all("acceptable" not in o.model_dump() for o in first)
            rejected = [Decision(clause_id=c, decision="reject", reason="r") for c in ids]
            second = landlord.respond(task, persona, rejected)
            assert second == landlord.respond(task, persona, rejected)
            assert [o.move_id for o in second] == [task["landlord_moves"][c][persona][1]["move_id"] for c in ids]
            accepted = landlord.respond(task, persona, [Decision(clause_id=ids[0], decision="accept", reason="ok")])
            assert accepted[0].move_id == first[0].move_id
            for clause_id in ids:  # the hidden flags follow the section 3 rules under default limits
                for move in task["landlord_moves"][clause_id][persona]:
                    assert landlord.within_limits(move["terms"], TenantLimits()) is move["acceptable"], move["move_id"]
    assert landlord.task_for_clauses(read_agreement(BLR["agreement_text"])["clauses"])["id"] == "blr_flat"
    assert landlord.task_for_clauses(read_agreement("C1. Rent is INR 9000.")["clauses"]) is None


def test_limits_override_flips_an_accept_on_a_four_month_lock_in() -> None:
    state = state_for(BLR, decide_model(lambda offer: ("accept", None)))
    result = negotiate(state, BLR, FINDINGS, False)

    second = {d.clause_id: d for d in result.rounds[1].decisions}
    assert result.rounds[1].offers[[o.clause_id for o in result.rounds[1].offers].index("C3")].terms == {"lock_in_months": 4}
    assert second["C3"].decision == "reject" and second["C3"].limit_override is True
    assert second["C3"].reason == "exceeds tenant limit: max_lock_in_months"
    first = {d.clause_id: d for d in result.rounds[0].decisions}
    assert first["C6"].decision == "accept" and not first["C6"].limit_override  # notice is not a tenant limit
    assert "C3" in result.open_clauses and result.status == "stalled"
    assert result.agreed_terms["C3"]["lock_in_months"] == 3 and result.agreed_terms["C3"]["ask"] == "Cap the lock-in."
    assert result.agreed_terms["C4"] == {"painting_inr": 8000}
    assert len(state.provider_chat.calls) == 2 and state.tool_calls == 2
    assert [s.type for s in state.trace] == ["landlord_offer", "tenant_decision", "landlord_offer", "tenant_decision", "negotiation_settled"]


def test_verifier_blocks_a_rent_act_citation_on_blr_flat() -> None:
    sections = {"C2": "KRA-15", "C3": None, "C4": "TPA-108(m)", "C6": "MTA-30"}
    state = state_for(BLR, decide_model(lambda offer: ("reject", sections[offer["clause_id"]])))
    result = negotiate(state, BLR, FINDINGS, False)

    verdicts = {d.clause_id: d.verdict for d in result.rounds[0].decisions}
    assert verdicts == {"C2": "blocked", "C3": "unverified", "C4": "cited", "C6": "blocked"}
    assert all(d.decision == "reject" for d in result.rounds[0].decisions)  # kept, with the verdict set


def test_fallback_decides_by_rule_when_the_model_fails() -> None:
    def down(messages, tools):
        raise ProviderError("timed out")

    state = state_for(BLR, down)
    result = negotiate(state, BLR, FINDINGS, False)

    assert all(r.fallback for r in result.rounds) and len(result.rounds) == 2
    first = {d.clause_id: d for d in result.rounds[0].decisions}
    assert first["C3"].decision == "reject" and first["C3"].reason == FALLBACK_REASON
    assert first["C3"].section_id == "ICA-74" and first["C3"].verdict == "cited"
    second = {d.clause_id: d.decision for d in result.rounds[1].decisions}
    assert second == {"C2": "accept", "C3": "reject", "C4": "accept", "C6": "accept"}
    assert any(s.type == "tenant_decision" and s.data.get("error") == "timed out" for s in state.trace)
    assert negotiation_correct(BLR, result.model_dump()) == 1.0


def test_entry_clause_falls_back_to_quiet_enjoyment_when_the_rent_act_is_unresolved() -> None:
    def down(messages, tools):
        raise ProviderError("offline")

    result = negotiate(state_for(PG, down), PG, [], None)
    entry = next(d for d in result.rounds[0].decisions if d.clause_id == "C5")
    assert entry.decision == "reject" and entry.section_id == "TPA-108(c)"
    assert result.agreed_terms["C3"] == {"painting_inr": 3000}  # Rs 3,000 cleaning is within the limit


def test_scorer_negotiation_correct() -> None:
    perfect = negotiate(state_for(BLR, decide_model(
        lambda o: ("accept" if landlord.is_acceptable(o["move_id"], BLR) else "reject", "ICA-74"))), BLR, FINDINGS, False)
    assert negotiation_correct(BLR, perfect.model_dump()) == 1.0
    accept_all = negotiate(state_for(BLR, decide_model(lambda o: ("accept", None))), BLR, FINDINGS, False, enforce=False)
    assert negotiation_correct(BLR, accept_all.model_dump()) < 0.5
    assert negotiation_correct(BLR, None) == 0.0
    assert negotiation_correct(json.loads((TASKS / "moveout.json").read_text(encoding="utf-8")), None) is None


@pytest.fixture()
def client(monkeypatch):
    agent = scripted_model(BLR_FINDINGS, [])
    decide = decide_model(lambda o: ("accept" if landlord.is_acceptable(o["move_id"], BLR) else "reject", "ICA-74"))
    monkeypatch.setattr(main, "provider_chat", lambda messages, tools: (decide if tools[0]["function"]["name"] == "decide_offers" else agent)(messages, tools))
    main.RUNS.clear()
    return TestClient(main.app)


def test_api_negotiates_then_approves_the_agreed_terms(client) -> None:
    body = {"agreement_text": BLR["agreement_text"], "facts": BLR["facts"], "persona": "reasonable_broker",
            "limits": {"max_lock_in_months": 3, "refund_within_days": 30, "max_exit_painting_inr": 10000}}
    run_id = client.post("/api/runs", json=body).json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()

    negotiation = run["negotiation"]
    assert run["status"] == "ready" and negotiation["persona"] == "reasonable_broker"
    assert negotiation["status"] == "settled" and negotiation["open_clauses"] == []
    assert negotiation["agreed_terms"]["C3"] == {"lock_in_months": 3}
    assert {"landlord_offer", "tenant_decision", "negotiation_settled"} <= {s["type"] for s in run["trace"]}

    stale = {**negotiation["agreed_terms"], "C3": {"lock_in_months": 6}}
    assert client.post(f"/api/runs/{run_id}/approve", json={"approved": True, "agreed_terms": stale}).status_code == 409
    approved = client.post(f"/api/runs/{run_id}/approve", json={"approved": True, "agreed_terms": negotiation["agreed_terms"]}).json()
    assert approved["status"] == "approved"
    assert [d["language"] for d in approved["drafts"]] == ["en", "kn", "hi"]
    assert "C3 (agreed): a lock-in of 3 months." in approved["drafts"][0]["text"]
    assert approved["approval"]["message"] == approved["drafts"][0]["text"]


def test_api_unknown_agreement_has_no_negotiation(client) -> None:
    text = BLR["agreement_text"].replace("INR 15000", "INR 12000")
    run_id = client.post("/api/runs", json={"agreement_text": text, "facts": BLR["facts"]}).json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "ready" and run["negotiation"] is None
    assert client.post(f"/api/runs/{run_id}/approve", json={"approved": True}).json()["status"] == "approved"


def test_verifier_blocks_a_rent_act_citation_while_coverage_is_unresolved() -> None:
    state = state_for(PG, decide_model(lambda offer: ("reject", "KRA-48(3)" if offer["clause_id"] == "C5" else "ICA-74")))
    result = negotiate(state, PG, [], None)

    verdicts = {d.clause_id: d.verdict for d in result.rounds[0].decisions}
    assert verdicts == {"C2": "cited", "C3": "cited", "C5": "blocked"}
    covered = negotiate(state_for(PG, decide_model(lambda offer: ("reject", "KRA-48(3)"))), PG, [], True)
    assert covered.rounds[0].decisions[0].verdict == "cited"  # the Act applies: the section may be cited
