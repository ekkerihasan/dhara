"""Agentic Flow 1 loop for agreement review.

The model reads the redacted clauses and drives the review through tool calls;
every tool result goes back to it before its next step. Deterministic tools and
the verifier stay the source of truth: the model never sets a rupee amount or
decides whether a section applies. If the model is unreachable, a rule-based
pass over the clauses runs instead and the trace says so.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from backend.agent.verifier import verify_claims
from backend.llm.provider import ProviderError, ToolCallOrText
from backend.agent import scripted_landlord as landlord
from backend.agent.negotiation import letter_items, run_negotiation
from backend.models import Draft, Finding, Negotiation, RunResponse, TenantLimits, TraceStep
from backend.tools.agreement import redact_pii
from backend.tools.law import LAW_PATH, check_jurisdiction, lookup_section
from backend.tools.messages import draft_message, send_and_schedule
from backend.tools.money import compute_money

LOGGER = logging.getLogger(__name__)
MAX_TOOL_CALLS = 12
MAX_MODEL_TURNS = 8
# Facts a tenant can actually answer; the agent pauses only for these.
ASKABLE_FACTS = ("rent_per_month", "built_year", "local_body", "premises_use", "completion_month")
FINDING_CATEGORIES = ("deposit_forfeiture", "lock_in", "painting_or_cleaning_fixed", "notice_shortfall", "rent_escalation_excess")
NOT_A_LAWYER_NOTICE = "Dhara AI is not a lawyer. Verify important decisions with a qualified professional."

ProviderChat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], ToolCallOrText]

MONEY_INPUTS = (
    "deposit_forfeiture: deposit (number), on_any_breach (bool), on_early_exit (bool). "
    "lock_in: monthly_rent, remaining_months. painting_or_cleaning_fixed: amount. "
    "notice_shortfall: monthly_rent, required_months, given_months. "
    "rent_escalation_excess: monthly_rent, escalation_percent (yearly)."
)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "record_finding",
        "description": "Record one unfair clause. The rupee amount is computed by Dhara from your inputs; never state it yourself. "
                       "Sections not in the law pack, or not applicable in Karnataka, are dropped.",
        "parameters": {"type": "object", "properties": {
            "clause_ref": {"type": "string", "description": "The clause id, e.g. C2"},
            "category": {"type": "string", "enum": list(FINDING_CATEGORIES)},
            "inputs": {"type": "object", "description": "Numbers read from the clause. " + MONEY_INPUTS},
            "section_ids": {"type": "array", "items": {"type": "string"}},
            "issue": {"type": "string", "description": "One plain sentence: why the clause is unfair to the tenant"},
            "ask": {"type": "string", "description": "One plain sentence: the change the tenant should request"},
        }, "required": ["clause_ref", "category", "inputs", "section_ids", "issue", "ask"]}}},
    {"type": "function", "function": {
        "name": "lookup_section",
        "description": "Look up a section in the Karnataka law pack before citing it.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End the review. List every legal claim you want to make; each is checked before the tenant sees it.",
        "parameters": {"type": "object", "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "section_id": {"type": ["string", "null"]}}, "required": ["text"]}}},
            "required": ["claims"]}}},
]


def _law_index() -> str:
    """Section ids the model may cite, each with the law pack's one-line paraphrase, one per line."""
    entries = json.loads(LAW_PATH.read_text(encoding="utf-8"))
    return "\n".join(f"{e['id']}: {e['title']}. {e.get('paraphrase', '')}" + ("" if e["applies_in_karnataka"] else " (NOT applicable in Karnataka)") for e in entries)


SYSTEM_PROMPT = """You review a residential rental agreement in Karnataka for the tenant.
1. Read every clause. For each clause that can cost the tenant money, call record_finding once, with the numbers you read from the clause text. Categories and their inputs: {money}
2. Cite only section ids from this list, and never cite one marked NOT applicable:
{law}
   Usual sections: deposit_forfeiture and lock_in -> ICA-74; painting_or_cleaning_fixed -> TPA-108(m) and ICA-74; notice_shortfall -> TPA-106.
   Record rent_escalation_excess for any yearly increase above 10 percent, always with section_ids [].
   If the Rent Act result says the Act does not apply, do not cite any KRA section for a finding.
3. Never state a rupee amount, a legal limit or a deadline yourself; the tools compute amounts.
   Karnataka has no statutory cap on deposits or rent increases. The 10 percent escalation figure is Dhara's fairness threshold, not a law.
   Every issue, ask and claim says no more than its section's paraphrase above, applied to the clause. Never call a clause illegal,
   unlawful, void, "not permitted", "not permissible", "prohibited" or a violation. Example: "C2 forfeits the whole deposit; under
   ICA-74 a landlord can recover only reasonable compensation, not the full stipulated amount."
4. When every unfair clause is recorded, call finish with your legal claims, each with the section_id it relies on (or null if none).
The Rent Act result for this flat is given to you; do not re-decide it."""


@dataclass
class AgentState:
    """Mutable in-memory state for one review run."""

    id: str
    clauses: list[dict[str, Any]]
    facts: dict[str, Any]
    language: str
    provider_chat: ProviderChat
    status: str = "running"
    trace: list[TraceStep] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    drafts: list[Draft] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    verdicts: list[dict[str, Any]] = field(default_factory=list)
    question: str | None = None
    approval: dict[str, Any] | None = None
    error: str | None = None
    tool_calls: int = 0
    seen_calls: set[str] = field(default_factory=set)
    tool_results: dict[str, Any] = field(default_factory=dict)
    rent_act_applies: bool | None = None
    unknown_facts: set[str] = field(default_factory=set)  # the tenant answered "I don't know"
    limits: TenantLimits = field(default_factory=TenantLimits)
    persona: str = "strict_owner"
    negotiation: Negotiation | None = None
    mode: Literal["agent", "baseline"] = "agent"
    baseline_output: dict[str, Any] | None = None

    def add_trace(self, trace_type: str, label: str, **data: Any) -> None:
        self.trace.append(TraceStep(type=trace_type, label=label, data=data))

    def response(self) -> RunResponse:
        return RunResponse(id=self.id, status=self.status, trace=self.trace, findings=self.findings,
                           drafts=self.drafts, question=self.question, claims=self.claims,
                           verdicts=self.verdicts, approval=self.approval, error=self.error,
                           mode=self.mode, baseline_output=self.baseline_output,
                           not_a_lawyer=True, notice=NOT_A_LAWYER_NOTICE, negotiation=self.negotiation)


def _safe_model_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii(value)[0]
    if isinstance(value, list):
        return [_safe_model_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_model_value(item) for key, item in value.items()}
    return value


def _call_key(name: str, arguments: dict[str, Any]) -> str:
    return json.dumps([name, arguments], sort_keys=True, ensure_ascii=False)


def _dispatch(state: AgentState, name: str, arguments: dict[str, Any], counted: bool = True) -> Any:
    """Dispatch one tool call and record it, failing closed on repeats.

    The 12-call budget limits the model-driven loop; the rule-based fallback passes counted=False.
    """
    if counted and state.tool_calls >= MAX_TOOL_CALLS:
        raise RuntimeError("Maximum of 12 tool calls reached")
    key = _call_key(name, arguments)
    if key in state.seen_calls:
        state.add_trace("tool_call", "Blocked repeated tool call", tool=name, inputs=_safe_model_value(arguments), error="Identical repeated tool call blocked")
        return state.tool_results.get(key)
    state.seen_calls.add(key)
    state.tool_calls += counted
    safe_arguments = _safe_model_value(arguments)
    LOGGER.info("agent tool_call name=%s inputs=%s", name, str(safe_arguments)[:200])
    try:
        if name == "check_jurisdiction":
            facts = safe_arguments.get("facts", safe_arguments)
            required = {key: facts.get(key) for key in ("rent_per_month", "built_year", "local_body", "premises_use")}
            optional = {key: value for key, value in facts.items() if key not in required}
            result = check_jurisdiction(**required, **optional)
        elif name == "lookup_section":
            result = lookup_section(safe_arguments["id"])
        elif name == "compute_money":
            result = {"money_at_risk_inr": compute_money(safe_arguments["finding_type"], safe_arguments["inputs"])}
        elif name == "record_finding":
            result = _record_finding(state, safe_arguments)
        elif name == "draft_message":
            result = draft_message(safe_arguments["findings"], safe_arguments["tone"], safe_arguments["language"])
        else:
            raise ValueError(f"Unknown tool: {name}")
    except (KeyError, TypeError, ValueError, PermissionError) as exc:
        result = {"error": str(exc)}
    state.add_trace("tool_call", name, tool=name, inputs=safe_arguments, output=result)
    state.tool_results[key] = result
    return result


def _citable(state: AgentState, section_id: str | None) -> bool:
    """A section may back a finding only if it is in the pack, applies in Karnataka and covers this flat."""
    section = lookup_section(section_id) if section_id else None
    if not section or not section["applies_in_karnataka"]:
        return False
    return not (state.rent_act_applies is False and section_id.startswith("KRA-"))


def _record_finding(state: AgentState, arguments: dict[str, Any]) -> dict[str, Any]:
    """Price a model-proposed finding with compute_money and keep only applicable sections."""
    clause_ref = str(arguments["clause_ref"])
    if _clause(state, clause_ref) is None:
        raise ValueError(f"Unknown clause {clause_ref}")
    category = arguments["category"]
    if category not in FINDING_CATEGORIES:
        raise ValueError(f"Unsupported category {category}")
    if any(f.clause_ref == clause_ref and f.category == category for f in state.findings):
        raise ValueError(f"{clause_ref} {category} is already recorded")
    amount = compute_money(category, arguments["inputs"])
    kept, dropped = [], []
    for section_id in arguments.get("section_ids", []):
        (kept if _citable(state, section_id) and category != "rent_escalation_excess" else dropped).append(section_id)
    state.findings.append(Finding(clause_ref=clause_ref, category=category, issue=str(arguments["issue"]),
                                  clause_text=_clause(state, clause_ref)["text"],
                                  ask=str(arguments.get("ask", "")), money_at_risk_inr=amount, section_ids=kept))
    return {"money_at_risk_inr": amount, "section_ids": kept, "dropped_section_ids": dropped}


def _number(text: str, pattern: str, default: float | None = None) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return default
    token = match.group(1).replace(",", "").casefold()
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    try:
        return float(words[token]) if token in words else float(token)
    except ValueError:
        return default


def _clause(state: AgentState, clause_id: str) -> dict[str, Any] | None:
    return next((clause for clause in state.clauses if clause["id"] == clause_id), None)


def _deterministic_findings(state: AgentState) -> list[dict[str, Any]]:
    """Extract only explicit priced obligations; ambiguous clauses stay with the model."""
    all_text = " ".join(clause["text"] for clause in state.clauses)
    monthly_rent = _number(all_text, r"monthly rent is INR\s*([\d,]+)")
    deposit = _number(all_text, r"deposit is INR\s*([\d,]+)")
    results: list[dict[str, Any]] = []
    for clause in state.clauses:
        text = clause["text"]
        lowered = text.casefold()
        category: str | None = None
        inputs: dict[str, Any] = {}
        sections: list[str] = []
        issue = ""
        negated = bool(re.search(r"\b(?:no|not|never|without)\b.{0,35}\b(?:forfeit\w*|lock[- ]in|painting|cleaning)\b", lowered))
        if negated:
            continue
        full_forfeiture = re.search(r"\b(?:entire|full|whole)\s+(?:(?:security|refundable)\s+)?deposit\b", lowered)
        if full_forfeiture and "forfeit" in lowered and ("breach" in lowered or "early exit" in lowered) and deposit is not None:
            category, inputs, sections = "deposit_forfeiture", {"deposit": deposit, "on_any_breach": "breach" in lowered, "on_early_exit": "early exit" in lowered}, ["ICA-74"]
            issue = "The clause allows the full deposit to be forfeited on breach or early exit; assess reasonable compensation rather than automatic forfeiture."
            ask = "Replace automatic forfeiture with deductions supported by documented loss and reasonable compensation."
        elif "lock-in" in lowered or "lock in" in lowered:
            months = _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+lock[- ]in months")
            if monthly_rent is not None and months is not None:
                category, inputs, sections = "lock_in", {"monthly_rent": monthly_rent, "remaining_months": months}, ["ICA-74"]
                issue = "The remaining lock-in exposure is calculated as rent for the stated remaining months; the clause needs a reasonable-compensation review."
                ask = "Limit any early-exit payment to reasonable, evidenced loss rather than the full remaining lock-in."
        elif (re.search(r"\b(?:fixed|exit|departure|deduct\w*|vacat\w*)\b", lowered)
              and (amount := _number(text, r"(?:painting|cleaning)\s+(?:charge|fee|cost)(?:\s+of|\s+is|\s*:)?\s+INR\s*([\d,]+)")) is not None):
            category, inputs, sections = "painting_or_cleaning_fixed", {"amount": amount}, ["TPA-108(m)", "ICA-74"]
            issue = "A fixed exit charge should be tied to evidenced damage or cleaning beyond reasonable wear and tear."
            ask = "Charge only for documented damage or cleaning beyond reasonable wear and tear."
        elif ("escalation" in lowered and re.search(r"\b(?:annual|annually|yearly)\b|\bper year\b", lowered)
              and (percent := _number(text, r"([\d.]+)\s*percent")) is not None and monthly_rent is not None and percent > 10):
            category, inputs, sections = "rent_escalation_excess", {"monthly_rent": monthly_rent, "escalation_percent": percent}, []
            issue = "The escalation exceeds Dhara's 10 percent product-review threshold; discuss whether the commercial term is acceptable."
            ask = "Ask to discuss a lower annual escalation; 10 percent is a product threshold, not a legal limit."
        elif "notice" in lowered and (required := _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+months?'? notice")) is not None:
            given = _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+month has been given")
            if given is not None and given < required and monthly_rent is not None:
                category, inputs, sections = "notice_shortfall", {"monthly_rent": monthly_rent, "required_months": required, "given_months": given}, ["TPA-106"]
                issue = "The stated notice is shorter than the agreement's required notice; check the contract and applicable default rules."
                ask = "Confirm the notice obligation and any lawful shortfall against the written agreement."
        if category:
            try:
                amount = compute_money(category, inputs)
            except ValueError:
                # An ambiguous or out-of-range extraction must not discard a
                # successful model review, or prevent checking the next clause.
                continue
            results.append({"clause_ref": clause["id"], "clause_text": text, "category": category, "issue": issue, "ask": ask,
                            "money_at_risk_inr": amount, "section_ids": sections})
    return results


def _ask_for_missing(state: AgentState, jurisdiction: dict[str, Any]) -> bool:
    """Pause only for facts a tenant can answer; other gaps stay visible as unresolved reasons."""
    if jurisdiction.get("applies") is not None:
        return False
    needed = set(jurisdiction.get("missing") or [])
    missing = [key for key in ASKABLE_FACTS
               if key in needed and state.facts.get(key) is None and key not in state.unknown_facts]
    if not missing:
        return False
    labels = ", ".join(missing)
    state.question = f"Please provide the missing tenancy fact(s): {labels}."
    state.status = "needs_input"
    state.add_trace("question", "Missing jurisdiction facts", missing=missing, question=state.question)
    return True


def _run_model_loop(state: AgentState, jurisdiction: dict[str, Any]) -> None:
    """Let the model drive the review: each tool result goes back to it until it calls finish."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(money=MONEY_INPUTS, law=_law_index())},
        {"role": "user", "content": json.dumps(_safe_model_value({"clauses": state.clauses, "facts": state.facts,
                                                                  "rent_act": jurisdiction}), ensure_ascii=False)},
    ]
    for _turn in range(MAX_MODEL_TURNS):
        result = state.provider_chat(messages, TOOL_SCHEMAS)
        if not result.tool_calls:
            if result.text:
                state.claims.append({"text": redact_pii(result.text)[0], "section_id": None})
            return
        messages.append({"role": "assistant", "content": result.text or "", "tool_calls": [
            {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
            for call in result.tool_calls]})
        for call in result.tool_calls:
            if call.name == "finish":
                for claim in call.arguments.get("claims", []):
                    state.claims.append({"text": redact_pii(str(claim.get("text", "")))[0], "section_id": claim.get("section_id")})
                state.add_trace("tool_call", "finish", tool="finish", inputs={"claims": len(call.arguments.get("claims", []))}, output="review complete")
                return
            try:
                output = _dispatch(state, call.name, call.arguments)
            except RuntimeError as exc:
                state.add_trace("tool_call", "Blocked tool call", tool=call.name, error=str(exc))
                return
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(output, ensure_ascii=False, default=str)})


def _rule_based_findings(state: AgentState) -> None:
    """Fill omitted, explicitly priced clauses using the bounded rule-based pass.

    This also runs after successful model reviews: a model calling finish early
    must not hide a charge that the deterministic extractor can establish.
    Existing model findings are preserved; no evaluation expectations are read.
    """
    covered = {(f.clause_ref, f.category) for f in state.findings}
    raw_findings = [raw for raw in _deterministic_findings(state) if (raw["clause_ref"], raw["category"]) not in covered]
    if not raw_findings:
        return
    state.add_trace("plan", "Rule-based coverage check", added=[
        {"clause_ref": raw["clause_ref"], "category": raw["category"]} for raw in raw_findings])
    known: dict[str, bool] = {}  # look each section up once, so the trace has no repeated calls
    for raw in raw_findings:
        for section_id in raw["section_ids"]:
            if section_id not in known:
                known[section_id] = _dispatch(state, "lookup_section", {"id": section_id}, counted=False) is not None
        raw["section_ids"] = [section_id for section_id in raw["section_ids"] if known[section_id] and _citable(state, section_id)]
        raw["source"] = "rule_based_coverage"
    state.findings += [Finding(**finding) for finding in raw_findings]


def _finish_analysis(state: AgentState) -> None:
    for finding in state.findings:
        state.claims.append({"text": finding.issue, "section_id": finding.section_ids[0] if finding.section_ids else None})
    state.verdicts = [verdict.model_dump() for verdict in verify_claims(state.claims)]
    for verdict in state.verdicts:
        section_id = verdict.get("section_id") or ""
        if verdict["verdict"] == "cited" and state.rent_act_applies is False and section_id.startswith("KRA-") and not section_id.startswith("KRA-2("):
            verdict["verdict"], verdict["reason"] = "blocked", "The Karnataka Rent Act does not apply to this flat, so this section cannot support the claim"
    for verdict in state.verdicts:
        state.add_trace("verifier", "Claim checked", claim=verdict)
    draft_input = [finding.model_dump() for finding in state.findings]
    # Both languages, the tenant's choice first, so the screen can switch between them.
    state.drafts = []
    for language in dict.fromkeys([state.language, "en", "kn", "hi"]):
        draft_result = _dispatch(state, "draft_message", {"findings": draft_input, "tone": "request", "language": language}, counted=False)
        if "error" not in draft_result:
            state.drafts.append(Draft(**draft_result))
            state.add_trace("draft", "Tenant draft prepared", draft=draft_result)
    state.status = "ready"
    state.question = None


def start_agent(state: AgentState) -> AgentResponse:
    """Run or resume the loop until it needs tenant input or approval."""
    state.add_trace("plan", "Review agreement", intended_tools=[schema["function"]["name"] for schema in TOOL_SCHEMAS])
    jurisdiction = _dispatch(state, "check_jurisdiction", state.facts)
    if _ask_for_missing(state, jurisdiction):
        return state.response()
    state.add_trace("tool_call", "Jurisdiction selected", output=jurisdiction)
    state.rent_act_applies = jurisdiction.get("applies")
    try:
        state.findings, state.claims = [], []
        try:
            _run_model_loop(state, jurisdiction)
        except ProviderError as exc:
            state.add_trace("tool_call", "Model unavailable: rule-based fallback", error=str(exc))
        _rule_based_findings(state)  # also recovers priced clauses the model skipped
        # Demo agreements only: the scripted landlord knows their clauses. Marked running before the
        # review turns ready, so approval waits for the negotiation.
        task = landlord.task_for_clauses(state.clauses) if state.findings else None
        if task is not None:
            state.negotiation = Negotiation(persona=state.persona, limits=state.limits)
        _finish_analysis(state)
        if task is not None:
            run_negotiation(state, task)
    except Exception as exc:
        LOGGER.exception("tenant agent failed")
        state.status = "failed"
        state.error = "The tenancy review could not be completed safely."
        state.add_trace("approval", "Run failed", error=str(exc))
    return state.response()


def _agreed_drafts(state: AgentState, agreed_terms: dict[str, Any] | None) -> None:
    """Replace the drafts with the letter for the negotiated outcome, in the tenant's language first."""
    negotiation = state.negotiation
    if negotiation.status == "running":
        raise ValueError("The negotiation is still running")
    if agreed_terms is not None and agreed_terms != negotiation.agreed_terms:
        raise ValueError("The agreed terms have changed; review them and approve again")
    items = letter_items(negotiation, [finding.model_dump() for finding in state.findings])
    drafts = []
    for language in dict.fromkeys([state.language, "en", "kn", "hi"]):
        draft = _dispatch(state, "draft_message", {"findings": items, "tone": "request", "language": language}, counted=False)
        if "error" not in draft:
            drafts.append(Draft(**draft))
    if drafts:
        state.drafts = drafts


def approve_agent(state: AgentState, agreed_terms: dict[str, Any] | None = None) -> RunResponse:
    if state.status != "ready" or not state.drafts:
        raise ValueError("A ready draft is required before approval")
    if state.negotiation is not None:
        _agreed_drafts(state, agreed_terms)
    record = send_and_schedule(state.drafts[0].text, True)
    state.approval = record
    state.status = "approved"
    state.add_trace("approval", "Tenant approved draft", approval=record)
    return state.response()


# Alias keeps the type name readable in the public function signatures.
AgentResponse = RunResponse
