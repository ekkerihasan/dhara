"""Agentic Flow 1 loop for agreement review.

The model proposes tool calls, while deterministic tools and the verifier remain
the source of truth for legal coverage and money-at-risk values.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.agent.verifier import verify_claims
from backend.llm.provider import ToolCallOrText
from backend.models import Draft, Finding, RunResponse, TraceStep
from backend.tools.agreement import redact_pii
from backend.tools.law import check_jurisdiction, lookup_section
from backend.tools.messages import draft_message, send_and_schedule
from backend.tools.money import compute_money

LOGGER = logging.getLogger(__name__)
MAX_TOOL_CALLS = 12
NOT_A_LAWYER_NOTICE = "Dhara AI is not a lawyer. Verify important decisions with a qualified professional."

ProviderChat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], ToolCallOrText]

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "check_jurisdiction", "description": "Screen Karnataka Rent Act coverage from supplied facts.", "parameters": {"type": "object", "properties": {"facts": {"type": "object"}}, "required": ["facts"]}}},
    {"type": "function", "function": {"name": "lookup_section", "description": "Look up a section in the Karnataka law pack.", "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
    {"type": "function", "function": {"name": "compute_money", "description": "Compute deterministic INR exposure for a finding.", "parameters": {"type": "object", "properties": {"finding_type": {"type": "string"}, "inputs": {"type": "object"}}, "required": ["finding_type", "inputs"]}}},
    {"type": "function", "function": {"name": "draft_message", "description": "Draft a structured tenant request in English or Kannada.", "parameters": {"type": "object", "properties": {"findings": {"type": "array"}, "tone": {"type": "string"}, "language": {"type": "string"}}, "required": ["findings", "tone", "language"]}}},
]


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

    def add_trace(self, trace_type: str, label: str, **data: Any) -> None:
        self.trace.append(TraceStep(type=trace_type, label=label, data=data))

    def response(self) -> RunResponse:
        return RunResponse(id=self.id, status=self.status, trace=self.trace, findings=self.findings,
                           drafts=self.drafts, question=self.question, claims=self.claims,
                           verdicts=self.verdicts, approval=self.approval, error=self.error,
                           not_a_lawyer=True, notice=NOT_A_LAWYER_NOTICE)


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


def _dispatch(state: AgentState, name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch one model tool call and record it, failing closed on repeats."""
    if state.tool_calls >= MAX_TOOL_CALLS:
        raise RuntimeError("Maximum of 12 tool calls reached")
    key = _call_key(name, arguments)
    if key in state.seen_calls:
        state.add_trace("tool_call", "Blocked repeated tool call", tool=name, inputs=_safe_model_value(arguments), error="Identical repeated tool call blocked")
        return state.tool_results.get(key)
    state.seen_calls.add(key)
    state.tool_calls += 1
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
        elif name == "draft_message":
            result = draft_message(safe_arguments["findings"], safe_arguments["tone"], safe_arguments["language"])
        else:
            raise ValueError(f"Unknown tool: {name}")
    except (KeyError, TypeError, ValueError, PermissionError) as exc:
        result = {"error": str(exc)}
    state.add_trace("tool_call", name, tool=name, inputs=safe_arguments, output=result)
    state.tool_results[key] = result
    return result


def _number(text: str, pattern: str, default: float | None = None) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return default
    token = match.group(1).replace(",", "").casefold()
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    return float(words[token]) if token in words else float(token)


def _clause(state: AgentState, clause_id: str) -> dict[str, Any] | None:
    return next((clause for clause in state.clauses if clause["id"] == clause_id), None)


def _deterministic_findings(state: AgentState) -> list[dict[str, Any]]:
    """Extract the bounded money categories used by the event scorer."""
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
        if "deposit" in lowered and ("forfeit" in lowered or "breach" in lowered or "early exit" in lowered) and deposit is not None:
            category, inputs, sections = "deposit_forfeiture", {"deposit": deposit, "on_any_breach": "breach" in lowered, "on_early_exit": "early exit" in lowered}, ["ICA-74"]
            issue = "The clause allows the full deposit to be forfeited on breach or early exit; assess reasonable compensation rather than automatic forfeiture."
        elif "lock-in" in lowered or "lock in" in lowered:
            months = _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+lock[- ]in months")
            if monthly_rent is not None and months is not None:
                category, inputs, sections = "lock_in", {"monthly_rent": monthly_rent, "remaining_months": months}, ["ICA-74"]
                issue = "The remaining lock-in exposure is calculated as rent for the stated remaining months; the clause needs a reasonable-compensation review."
        elif ("painting" in lowered or "cleaning" in lowered) and (amount := _number(text, r"INR\s*([\d,]+)")) is not None:
            category, inputs, sections = "painting_or_cleaning_fixed", {"amount": amount}, ["TPA-108(m)", "ICA-74"]
            issue = "A fixed exit charge should be tied to evidenced damage or cleaning beyond reasonable wear and tear."
        elif "escalation" in lowered and (percent := _number(text, r"([\d.]+)\s*percent")) is not None and monthly_rent is not None and percent > 10:
            category, inputs, sections = "rent_escalation_excess", {"monthly_rent": monthly_rent, "escalation_percent": percent}, []
            issue = "The escalation exceeds Dhara's 10 percent product-review threshold; discuss whether the commercial term is acceptable."
        elif "notice" in lowered and (required := _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+months?'? notice")) is not None:
            given = _number(text, r"([\d.]+|one|two|three|four|five|six|seven|eight|nine|ten)\s+month has been given")
            if given is not None and monthly_rent is not None:
                category, inputs, sections = "notice_shortfall", {"monthly_rent": monthly_rent, "required_months": required, "given_months": given}, ["TPA-106"]
                issue = "The stated notice is shorter than the agreement's required notice; check the contract and applicable default rules."
        if category:
            result = _dispatch(state, "compute_money", {"finding_type": category, "inputs": inputs})
            amount = int(result.get("money_at_risk_inr", 0))
            results.append({"clause_ref": clause["id"], "category": category, "issue": issue,
                            "money_at_risk_inr": amount, "section_ids": sections})
    return results


def _ask_for_missing(state: AgentState, jurisdiction: dict[str, Any]) -> bool:
    if jurisdiction.get("applies") is not None:
        return False
    missing = [str(item) for item in jurisdiction.get("missing", [])]
    if not missing:
        return False
    labels = ", ".join(missing)
    state.question = f"Please provide the missing tenancy fact(s): {labels}."
    state.status = "needs_input"
    state.add_trace("question", "Missing jurisdiction facts", missing=missing, question=state.question)
    return True


def _run_provider_advisory(state: AgentState) -> None:
    """Give the configured model a safe chance to use the registered tools."""
    messages = [
        {"role": "system", "content": "Review this redacted tenancy agreement. Use only registered tools for legal sections and money. Never cite the Model Tenancy Act as binding Karnataka law."},
        {"role": "user", "content": json.dumps(_safe_model_value({"clauses": state.clauses, "facts": state.facts}), ensure_ascii=False)},
    ]
    result = state.provider_chat(messages, TOOL_SCHEMAS)
    if result.text:
        state.claims.append({"text": redact_pii(result.text)[0], "section_id": None})
    for call in result.tool_calls:
        try:
            _dispatch(state, call.name, call.arguments)
        except RuntimeError as exc:
            state.add_trace("tool_call", "Blocked tool call", tool=call.name, error=str(exc))


def _finish_analysis(state: AgentState) -> None:
    raw_findings = _deterministic_findings(state)
    for raw in raw_findings:
        valid_sections: list[str] = []
        for section_id in raw["section_ids"]:
            section = _dispatch(state, "lookup_section", {"id": section_id})
            if section is not None:
                valid_sections.append(section_id)
        raw["section_ids"] = valid_sections
        state.claims.append({"text": raw["issue"], "section_id": valid_sections[0] if valid_sections else None})
    state.findings = [Finding(**finding) for finding in raw_findings]
    state.verdicts = [verdict.model_dump() for verdict in verify_claims(state.claims)]
    for verdict in state.verdicts:
        state.add_trace("verifier", "Claim checked", claim=verdict)
    draft_input = [finding.model_dump() for finding in state.findings]
    draft_result = _dispatch(state, "draft_message", {"findings": draft_input, "tone": "request", "language": state.language})
    if "error" not in draft_result:
        state.drafts = [Draft(**draft_result)]
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
    try:
        _run_provider_advisory(state)
        _finish_analysis(state)
    except Exception as exc:
        LOGGER.exception("tenant agent failed")
        state.status = "failed"
        state.error = "The tenancy review could not be completed safely."
        state.add_trace("approval", "Run failed", error=str(exc))
    return state.response()


def approve_agent(state: AgentState) -> RunResponse:
    if state.status != "ready" or not state.drafts:
        raise ValueError("A ready draft is required before approval")
    record = send_and_schedule(state.drafts[0].text, True)
    state.approval = record
    state.status = "approved"
    state.add_trace("approval", "Tenant approved draft", approval=record)
    return state.response()


# Alias keeps the type name readable in the public function signatures.
AgentResponse = RunResponse
