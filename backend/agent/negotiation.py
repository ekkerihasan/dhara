"""Two-round negotiation against the scripted landlord, after Flow 1 has its findings.

Per round: the landlord makes offers (backend/agent/landlord.py, no model), the tenant agent answers
every open clause in one decide_offers tool call, the verifier checks each reason's section id, and
code enforces the tenant's limits. The model never settles a clause past a limit: an accept that
breaches one is flipped to reject in code and marked limit_override. If the model is unavailable,
a rule decides the round and the trace says so. The tenant approves the agreed terms once at the end.
"""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from backend.agent import scripted_landlord as landlord
from backend.agent.verifier import verify_claims
from backend.llm.provider import ProviderError
from backend.models import Decision, Negotiation, NegotiationRound, Offer, TenantLimits
from backend.tools.agreement import redact_pii

if TYPE_CHECKING:
    from backend.agent.tenant import AgentState

LOGGER = logging.getLogger(__name__)
MAX_ROUNDS = 2
FALLBACK_REASON = "rule-based decision (model unavailable)"

DECIDE_TOOL: dict[str, Any] = {"type": "function", "function": {
    "name": "decide_offers",
    "description": "Answer every open landlord offer in one call: accept, reject or counter each.",
    "parameters": {"type": "object", "properties": {"decisions": {"type": "array", "items": {"type": "object", "properties": {
        "clause_id": {"type": "string"},
        "decision": {"type": "string", "enum": ["accept", "reject", "counter"]},
        "counter_terms": {"type": ["object", "null"], "description": "For a counter: the terms you propose, same keys as the offer"},
        "reason": {"type": "string", "description": "One plain sentence for the tenant"},
        "section_id": {"type": ["string", "null"], "description": "Required for reject or counter: a section id from the list"},
    }, "required": ["clause_id", "decision", "reason", "section_id"]}}}, "required": ["decisions"]}}}

SYSTEM_PROMPT = """You negotiate a residential rental agreement in Karnataka for the tenant, before signing.
The landlord has made one offer per open clause. Call decide_offers once, with one decision per offer:
- "accept" only if the offer's terms are within the tenant's limits and fair to the tenant;
- "reject" or "counter" otherwise. A counter gives counter_terms with the same keys as the offer.
The tenant's limits are their own preferences, not legal limits: never call them law.
Dhara's fairness standard (also not law): no forfeiture of the deposit on any breach, the same notice period for
both sides and no more than 2 months, and at least 24 hours' notice before the landlord enters.
Every reject or counter must cite one section id from this list, and never one marked NOT applicable:
{law}
Karnataka Rent Act (KRA) sections need the Rent Act result to say the Act applies; when it does not apply or is
unresolved, cite a non-KRA section instead (ICA, TPA or RA). A reject or counter still always needs a section id.
Never call a term illegal, unlawful, void, "not permitted", "not permissible", prohibited or a violation; say what
the cited section's paraphrase supports."""

# The section a rule-based decision cites when no finding names one, by term key.
DEFAULT_SECTIONS = {"lock_in_months": "ICA-74", "refund_within_days": "ICA-74", "painting_inr": "TPA-108(m)",
                    "tenant_notice_months": "TPA-106", "notice_hours": "TPA-108(c)"}


def _term_key(terms: dict[str, Any]) -> str | None:
    return next((key for key in DEFAULT_SECTIONS if key in terms), None)


def tenant_ask(offer: Offer, limits: TenantLimits, finding: dict[str, Any] | None) -> dict[str, Any]:
    """The tenant's standing ask for a clause that stays open: their limit, or the fair default."""
    key = _term_key(offer.terms)
    terms: dict[str, Any] = {
        "lock_in_months": {"lock_in_months": min(limits.max_lock_in_months, offer.terms.get("lock_in_months", 0))},
        "refund_within_days": {"refund_within_days": limits.refund_within_days, "forfeit_on_any_breach": False},
        "painting_inr": {"painting_inr": min(limits.max_exit_painting_inr, offer.terms.get("painting_inr", 0))},
        "tenant_notice_months": {"tenant_notice_months": 1, "landlord_notice_months": 1},
        "notice_hours": {"notice_hours": 24},
    }.get(key or "", {})
    if finding and finding.get("ask"):
        terms["ask"] = finding["ask"]
    return terms


def _rule_decision(offer: Offer, limits: TenantLimits, finding: dict[str, Any] | None, rent_act_applies: bool | None) -> Decision:
    """Accept if within limits, else reject citing the finding's best section."""
    if landlord.within_limits(offer.terms, limits):
        return Decision(clause_id=offer.clause_id, decision="accept", reason=FALLBACK_REASON, section_id=None)
    sections = (finding or {}).get("section_ids") or []
    key = _term_key(offer.terms)
    section = sections[0] if sections else ("KRA-48(3)" if key == "notice_hours" and rent_act_applies else DEFAULT_SECTIONS.get(key or ""))
    return Decision(clause_id=offer.clause_id, decision="reject", reason=FALLBACK_REASON, section_id=section)


def _verdict(decision: Decision, rent_act_applies: bool | None) -> str:
    """The verifier, unchanged, plus the Rent Act coverage rule: a KRA section needs confirmed coverage."""
    if not decision.section_id:
        return "unverified"
    checked = verify_claims([{"text": decision.reason, "section_id": decision.section_id}])[0]
    if checked.verdict == "blocked":
        return "blocked"
    if rent_act_applies is not True and decision.section_id.startswith("KRA-"):  # not covered, or unresolved
        return "blocked"
    return checked.verdict


def _enforce_limits(decision: Decision, offer: Offer, limits: TenantLimits) -> Decision:
    """Code, not the model, holds the tenant's limits: an accept past a limit becomes a reject."""
    field = landlord.limit_breach(offer.terms, limits)
    if decision.decision == "accept" and field:
        return decision.model_copy(update={"decision": "reject", "limit_override": True,
                                           "reason": f"exceeds tenant limit: {field}"})
    return decision


def _model_decisions(state: AgentState, offers: list[Offer], findings: list[dict[str, Any]],
                     rent_act_applies: bool | None) -> dict[str, Decision]:
    """One decide_offers call. Raises ProviderError when the model cannot be used for this round."""
    from backend.agent.tenant import MAX_TOOL_CALLS, _call_key, _law_index, _safe_model_value
    payload = {"findings": [{k: f.get(k) for k in ("clause_ref", "category", "ask", "section_ids")} for f in findings],
               "offers": [o.model_dump() for o in offers], "tenant_limits": state.limits.model_dump(),
               "rent_act": {"applies": rent_act_applies}}
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(law=_law_index())},
                {"role": "user", "content": json.dumps(_safe_model_value(payload), ensure_ascii=False)}]
    key = _call_key("decide_offers", {"messages": messages})
    if key in state.seen_calls:
        raise ProviderError("Identical repeated model call blocked")
    if state.tool_calls >= MAX_TOOL_CALLS:
        raise ProviderError("Maximum of 12 tool calls reached")
    state.seen_calls.add(key)
    state.tool_calls += 1
    result = state.provider_chat(messages, [DECIDE_TOOL])
    call = next((c for c in result.tool_calls if c.name == "decide_offers"), None)
    if call is None:
        raise ProviderError("Model did not call decide_offers")
    open_ids = {o.clause_id for o in offers}
    decisions: dict[str, Decision] = {}
    for raw in call.arguments.get("decisions", []):
        try:
            decision = Decision(clause_id=str(raw["clause_id"]), decision=raw["decision"],
                                counter_terms=raw.get("counter_terms") if isinstance(raw.get("counter_terms"), dict) else None,
                                reason=redact_pii(str(raw.get("reason", "")))[0][:500], section_id=raw.get("section_id") or None)
        except (KeyError, TypeError, ValueError):
            continue  # a malformed decision is decided by rule below
        if decision.clause_id in open_ids and decision.clause_id not in decisions:
            decisions[decision.clause_id] = decision
    return decisions


def _play_round(state: AgentState, number: int, offers: list[Offer], findings: dict[str, dict[str, Any]],
                rent_act_applies: bool | None, enforce: bool) -> NegotiationRound:
    """Offers in, decisions out: model first, rule for anything the model could not decide."""
    state.add_trace("landlord_offer", f"Round {number}: {landlord.PERSONA_LABELS[state.persona]} offers",
                    round=number, persona=state.persona, offers=[o.model_dump() for o in offers])
    error = None
    started = time.monotonic()
    try:
        decided = _model_decisions(state, offers, list(findings.values()), rent_act_applies)
    except Exception as exc:  # any failure of the model step: this round is decided by rule
        decided, error = {}, str(exc) or type(exc).__name__
    model_ms = int((time.monotonic() - started) * 1000)
    fallback = enforce and (error is not None or len(decided) < len(offers))
    decisions = []
    for offer in offers:
        decision = decided.get(offer.clause_id)
        if decision is None and not enforce:
            continue  # the baseline has no rule fallback: an offer it did not answer stays unanswered
        if decision is None:
            decision = _rule_decision(offer, state.limits, findings.get(offer.clause_id), rent_act_applies)
        if enforce:
            decision = decision.model_copy(update={"verdict": _verdict(decision, rent_act_applies)})
            decision = _enforce_limits(decision, offer, state.limits)
        decisions.append(decision)
    played = NegotiationRound(round=number, offers=offers, decisions=decisions, model_ms=model_ms, fallback=fallback)
    state.add_trace("tenant_decision", f"Round {number}: tenant decides" + (" (rule-based)" if fallback else ""),
                    round=number, decisions=[d.model_dump() for d in decisions], model_ms=model_ms, fallback=fallback,
                    **({"error": error} if error else {}))
    return played


def negotiate(state: AgentState, task: dict[str, Any], findings: list[dict[str, Any]],
              rent_act_applies: bool | None, *, enforce: bool = True) -> Negotiation:
    """Run up to two rounds on every clause the landlord has moves for; fills state.negotiation as it goes.

    enforce=False is the evaluation baseline: same offers and model, no verifier and no limits.
    """
    by_clause = {f["clause_ref"]: f for f in findings}
    clause_ids = list(task.get("landlord_moves", {}))
    negotiation = Negotiation(persona=state.persona, limits=state.limits)
    state.negotiation = negotiation
    offers = landlord.opening(task, state.persona, clause_ids)
    last_offer: dict[str, Offer] = {}
    accepted: dict[str, Offer] = {}
    for number in range(1, MAX_ROUNDS + 1):
        last_offer.update({o.clause_id: o for o in offers})
        played = _play_round(state, number, offers, by_clause, rent_act_applies, enforce)
        negotiation.rounds.append(played)
        accepted.update({d.clause_id: last_offer[d.clause_id] for d in played.decisions if d.decision == "accept"})
        still_open = [d for d in played.decisions if d.decision != "accept"]
        if not still_open or number == MAX_ROUNDS:
            break
        offers = landlord.respond(task, state.persona, still_open)
    open_ids = [c for c in clause_ids if c not in accepted]
    negotiation.agreed_terms = {c: dict(accepted[c].terms) if c in accepted else tenant_ask(last_offer[c], state.limits, by_clause.get(c))
                                for c in clause_ids}
    negotiation.settled_clauses = [c for c in clause_ids if c in accepted]
    negotiation.open_clauses = open_ids
    negotiation.status = "stalled" if open_ids else "settled"
    state.add_trace("negotiation_settled", f"Negotiation {negotiation.status}", agreed_terms=negotiation.agreed_terms,
                    settled_clauses=negotiation.settled_clauses, open_clauses=negotiation.open_clauses)
    return negotiation


def run_negotiation(state: AgentState, task: dict[str, Any]) -> Negotiation | None:
    """Called at the end of the tenant agent loop once findings exist."""
    try:
        return negotiate(state, task, [f.model_dump() for f in state.findings], state.rent_act_applies)
    except Exception as exc:  # the review itself stays usable; the trace keeps the cause
        LOGGER.exception("negotiation failed")
        if state.negotiation is not None:
            state.negotiation.status = "stalled"
        state.add_trace("negotiation_settled", "Negotiation stopped", error=str(exc))
        return state.negotiation


def letter_items(negotiation: Negotiation, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What draft_message needs for the approved letter: one item per negotiated clause."""
    categories = {f["clause_ref"]: f["category"] for f in findings}
    return [{"clause_ref": clause_id, "category": categories.get(clause_id),
             "terms": {k: v for k, v in terms.items() if k != "ask"}, "settled": clause_id in negotiation.settled_clauses}
            for clause_id, terms in negotiation.agreed_terms.items()]
