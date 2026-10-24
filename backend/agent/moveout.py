"""Flow 2: contest move-out deductions against the agreement and the dated move-in checklist.

The model reads the clauses, the checklist and the landlord's claimed deductions, and records a
verdict for each deduction through a tool call. Code checks the sections it cites, drafts the
challenge and picks the next formal step. If the model is unreachable, a rule pass runs instead:
wear and tear, and damage the checklist shows was there at move-in, are disputed.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.agent.tenant import ProviderChat, _law_index, _safe_model_value
from backend.llm.provider import ProviderError
from backend.models import Draft, TraceStep
from backend.tools.law import check_jurisdiction, lookup_section
from backend.tools.messages import draft_message, send_and_schedule

LOGGER = logging.getLogger(__name__)
MAX_MODEL_TURNS = 6
NOT_A_LAWYER_NOTICE = "Dhara AI is not a lawyer. Verify important decisions with a qualified professional."

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "record_verdict",
        "description": "Record your verdict on one claimed deduction. Cite the move-in checklist entries you relied on.",
        "parameters": {"type": "object", "properties": {
            "deduction_id": {"type": "string", "description": "e.g. D1"},
            "verdict": {"type": "string", "enum": ["allowed", "disputed"]},
            "reason": {"type": "string", "description": "One plain sentence, no more than the clause, the checklist and the section's paraphrase support"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "section_ids": {"type": "array", "items": {"type": "string"}},
        }, "required": ["deduction_id", "verdict", "reason", "evidence_ids", "section_ids"]}}},
    {"type": "function", "function": {
        "name": "finish", "description": "End the review once every deduction has a verdict.",
        "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM_PROMPT = """You check a landlord's move-out deductions for a tenant in Karnataka.
For every claimed deduction call record_verdict once:
- "allowed" when the agreement clearly permits that charge and the amount is within what it states;
- "disputed" when it charges for reasonable wear and tear, for a condition the move-in checklist shows was already there,
  or for damage with no dated evidence.
Cite only these section ids, never one marked NOT applicable, and no Rent Act (KRA) section if the Rent Act result says the Act does not apply:
{law}
Usual sections: wear and tear or pre-existing condition -> TPA-108(m); a charge beyond actual loss -> ICA-74.
Never call a charge illegal, unlawful, void, "not permitted", "not permissible" or a violation, and never state a deadline
or limit that is not in a clause. Say what the clause, the checklist and the section show. Then call finish."""


@dataclass
class MoveoutState:
    """Mutable in-memory state for one move-out review."""

    id: str
    clauses: list[dict[str, Any]]
    checklist: list[dict[str, Any]]
    deductions: list[dict[str, Any]]  # each: id, clause_ref, category, label, amount_inr, evidence_ids
    facts: dict[str, Any]
    language: str
    provider_chat: ProviderChat
    status: str = "running"
    trace: list[TraceStep] = field(default_factory=list)
    verdicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    drafts: list[Draft] = field(default_factory=list)
    next_steps: list[dict[str, str]] = field(default_factory=list)
    approval: dict[str, Any] | None = None
    rent_act_applies: bool | None = None
    error: str | None = None

    def add_trace(self, trace_type: str, label: str, **data: Any) -> None:
        self.trace.append(TraceStep(type=trace_type, label=label, data=data))

    def response(self) -> dict[str, Any]:
        deductions = [{**d, **self.verdicts.get(d["id"], {})} for d in self.deductions]
        disputed = sum(d["amount_inr"] for d in deductions if d.get("verdict") == "disputed")
        return {"id": self.id, "status": self.status, "trace": [s.model_dump() for s in self.trace],
                "deductions": deductions, "disputed_inr": disputed, "checklist": self.checklist,
                "drafts": [d.model_dump() for d in self.drafts], "next_steps": self.next_steps,
                "approval": self.approval, "error": self.error, "not_a_lawyer": True, "notice": NOT_A_LAWYER_NOTICE}


def _citable(state: MoveoutState, section_id: str) -> bool:
    section = lookup_section(section_id)
    if not section or not section["applies_in_karnataka"]:
        return False
    return not (state.rent_act_applies is False and section_id.startswith("KRA-"))


def _record(state: MoveoutState, arguments: dict[str, Any], source: str) -> dict[str, Any]:
    deduction_id = str(arguments.get("deduction_id"))
    if deduction_id not in {d["id"] for d in state.deductions}:
        return {"error": f"Unknown deduction {deduction_id}"}
    if arguments.get("verdict") not in {"allowed", "disputed"}:
        return {"error": "verdict must be allowed or disputed"}
    known_evidence = {e["id"] for e in state.checklist}
    sections = [s for s in arguments.get("section_ids", []) if _citable(state, s)]
    verdict = {"verdict": arguments["verdict"], "reason": str(arguments.get("reason", "")), "source": source,
               "evidence_ids": [e for e in arguments.get("evidence_ids", []) if e in known_evidence], "section_ids": sections}
    state.verdicts[deduction_id] = verdict
    state.add_trace("tool_call", "record_verdict", tool="record_verdict", inputs=_safe_model_value(arguments), output=verdict)
    return verdict


def _rule_verdicts(state: MoveoutState) -> None:
    """Fallback when the model is unreachable."""
    evidence = {e["id"]: e for e in state.checklist}
    for d in state.deductions:
        if d["id"] in state.verdicts:
            continue
        pre_existing = any(word in str(evidence.get(e, {}).get("condition", "")).casefold()
                           for e in d.get("evidence_ids", []) for word in ("already", "present", "ordinary", "wear"))
        if d["category"] == "wear_and_tear" or pre_existing:
            args = {"deduction_id": d["id"], "verdict": "disputed", "evidence_ids": d.get("evidence_ids", []), "section_ids": ["TPA-108(m)"],
                    "reason": "Reasonable wear and tear, or a condition recorded at move-in, is excepted from the restoration duty."}
        else:
            args = {"deduction_id": d["id"], "verdict": "allowed", "evidence_ids": [], "section_ids": [],
                    "reason": "The agreement provides for this charge and nothing in the checklist contradicts it."}
        _record(state, args, source="rules")


def _model_loop(state: MoveoutState, jurisdiction: dict[str, Any]) -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(law=_law_index())},
        {"role": "user", "content": json.dumps(_safe_model_value({"clauses": state.clauses, "move_in_checklist": state.checklist,
                                                                  "claimed_deductions": state.deductions, "rent_act": jurisdiction}), ensure_ascii=False)},
    ]
    for _turn in range(MAX_MODEL_TURNS):
        result = state.provider_chat(messages, TOOL_SCHEMAS)
        if not result.tool_calls:
            return
        messages.append({"role": "assistant", "content": result.text or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
            for c in result.tool_calls]})
        for call in result.tool_calls:
            if call.name == "finish":
                return
            output = _record(state, call.arguments, source="model") if call.name == "record_verdict" else {"error": f"Unknown tool {call.name}"}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(output, ensure_ascii=False)})


def next_formal_steps(rent_act_applies: bool | None) -> list[dict[str, str]]:
    """Recovery routes, in order (CLAUDE.md). Never a police complaint."""
    court = ({"title": "Rent Controller", "detail": "The Karnataka Rent Act covers this tenancy, so the claim goes to the Rent Controller.", "certainty": "established"}
             if rent_act_applies else
             {"title": "Civil money-recovery suit", "detail": "The Rent Act does not cover this flat, so the claim is a civil recovery suit; in Bengaluru, the Court of Small Causes within its pecuniary limit (limit unverified).", "certainty": "established"})
    return [
        {"title": "Written demand", "detail": "Send the approved challenge. Dhara records a follow-up 7 days later.", "certainty": "established"},
        {"title": "Legal notice", "detail": "If there is no refund, a firmer notice drafted from the same verdicts, preferably sent through an advocate.", "certainty": "established"},
        court,
        {"title": "Consumer forum (e-Daakhil)", "detail": "Whether a tenancy deposit dispute is a consumer complaint is contested. Shown for completeness only.", "certainty": "uncertain"},
    ]


def start_moveout(state: MoveoutState) -> dict[str, Any]:
    state.add_trace("plan", "Review move-out deductions", intended_tools=["check_jurisdiction", "record_verdict", "draft_message"])
    facts = state.facts
    jurisdiction = check_jurisdiction(facts.get("rent_per_month"), facts.get("built_year"), facts.get("local_body"), facts.get("premises_use"))
    state.rent_act_applies = jurisdiction.get("applies")
    state.add_trace("tool_call", "check_jurisdiction", tool="check_jurisdiction", inputs=_safe_model_value(facts), output=jurisdiction)
    try:
        try:
            _model_loop(state, jurisdiction)
        except ProviderError as exc:
            state.add_trace("tool_call", "Model unavailable: rule-based fallback", error=str(exc))
        _rule_verdicts(state)  # fills only deductions the model left without a verdict
        disputed = [{"clause_ref": d["clause_ref"], "category": d["category"]} for d in state.deductions if state.verdicts[d["id"]]["verdict"] == "disputed"]
        state.drafts = []
        for language in dict.fromkeys([state.language, "en", "kn", "hi"]):
            draft = draft_message(disputed, "challenge", language)
            state.drafts.append(Draft(**draft))
            state.add_trace("draft", "Challenge drafted", draft=draft)
        state.next_steps = next_formal_steps(state.rent_act_applies)
        state.status = "ready"
    except Exception as exc:  # the trace keeps the cause; the tenant sees a safe message
        LOGGER.exception("move-out review failed")
        state.status, state.error = "failed", "The move-out review could not be completed safely."
        state.add_trace("approval", "Run failed", error=str(exc))
    return state.response()


def approve_moveout(state: MoveoutState) -> dict[str, Any]:
    if state.status != "ready" or not state.drafts:
        raise ValueError("A ready challenge is required before approval")
    state.approval = send_and_schedule(state.drafts[0].text, True)
    state.status = "approved"
    state.add_trace("approval", "Tenant approved the challenge", approval=state.approval)
    return state.response()
