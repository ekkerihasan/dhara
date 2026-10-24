"""Pydantic schemas shared by the backend API and the frontend handoff."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Language = Literal["en", "kn", "hi"]
RunStatus = Literal["running", "needs_input", "ready", "approved", "failed"]
TraceType = Literal["plan", "question", "tool_call", "verifier", "draft", "approval",
                    "landlord_offer", "tenant_decision", "negotiation_settled", "needs_itemisation"]
LandlordPersona = Literal["strict_owner", "reasonable_broker"]


class PropertyFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rent_per_month: float | None = Field(default=None, ge=0)
    built_year: int | None = Field(default=None, ge=1)
    local_body: str | None = None
    premises_use: str | None = None
    substantial_renovation_year: int | None = Field(default=None, ge=1)
    completion_month: int | None = Field(default=None, ge=1, le=12)  # asked only when the building turns 15 this year
    standard_rent_monthly: float | None = Field(default=None, ge=0)
    ownership_type: str | None = None
    other_exemptions_checked: bool | None = None
    tenancy_date: str | None = None


class TenantLimits(BaseModel):
    """The tenant's own negotiating limits: preferences, not legal limits."""
    model_config = ConfigDict(extra="forbid")

    max_lock_in_months: int = Field(default=3, ge=0)
    refund_within_days: int = Field(default=30, ge=0)
    max_exit_painting_inr: int = Field(default=10000, ge=0)


class Offer(BaseModel):
    """One scripted landlord move on one clause; terms e.g. {"lock_in_months": 3}."""
    clause_id: str
    move_id: str
    text: str
    terms: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    clause_id: str
    decision: Literal["accept", "reject", "counter"]
    counter_terms: dict[str, Any] | None = None
    reason: str
    section_id: str | None = None
    verdict: Literal["cited", "unverified", "blocked"] = "unverified"
    limit_override: bool = False  # true when code flipped the model's accept to reject


class NegotiationRound(BaseModel):
    round: int
    offers: list[Offer] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    model_ms: int = 0
    fallback: bool = False


class Negotiation(BaseModel):
    persona: LandlordPersona
    limits: TenantLimits
    rounds: list[NegotiationRound] = Field(default_factory=list)
    status: Literal["running", "settled", "stalled"] = "running"
    agreed_terms: dict[str, dict[str, Any]] = Field(default_factory=dict)  # clause_id -> terms
    settled_clauses: list[str] = Field(default_factory=list)
    open_clauses: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreement_text: str | None = None
    pdf_base64: str | None = None
    facts: PropertyFacts = Field(default_factory=PropertyFacts)
    language: Language = "en"
    limits: TenantLimits = Field(default_factory=TenantLimits)
    persona: LandlordPersona = "strict_owner"


class ChecklistEntry(BaseModel):
    """One dated move-in checklist entry."""
    model_config = ConfigDict(extra="forbid")

    id: str
    date: str
    item: str
    condition: str
    evidence: str = ""


class ClaimedDeduction(BaseModel):
    """One deduction the landlord claims from the deposit."""
    model_config = ConfigDict(extra="forbid")

    clause_ref: str
    category: str
    label: str
    amount_inr: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class MoveoutRequest(BaseModel):
    """Itemised deductions, or the landlord's message as sent (claimed_text), e.g. "painting and repairs 80396"."""
    model_config = ConfigDict(extra="forbid")

    agreement_text: str
    checklist: list[ChecklistEntry] = Field(default_factory=list)
    deductions: list[ClaimedDeduction] = Field(default_factory=list)
    claimed_text: str | None = Field(default=None, max_length=4000)
    deposit_inr: int | None = Field(default=None, ge=0)
    facts: PropertyFacts = Field(default_factory=PropertyFacts)
    language: Language = "en"


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    agreed_terms: dict[str, dict[str, Any]] | None = None  # must match the negotiated terms the tenant saw


class TraceStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: TraceType
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    model_config = ConfigDict(extra="allow")

    clause_ref: str
    clause_text: str
    category: str
    issue: str
    ask: str
    money_at_risk_inr: int = Field(ge=0)
    section_ids: list[str] = Field(default_factory=list)


class Draft(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    language: Language
    tone: Literal["request", "challenge", "notice"]
    translation_note: str


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: RunStatus
    trace: list[TraceStep] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    drafts: list[Draft] = Field(default_factory=list)
    question: str | None = None
    claims: list[dict[str, Any]] = Field(default_factory=list)
    verdicts: list[dict[str, Any]] = Field(default_factory=list)
    approval: dict[str, Any] | None = None
    not_a_lawyer: bool = True
    notice: str = "Dhara AI is not a lawyer. Verify important decisions with a qualified professional."
    error: str | None = None
    negotiation: Negotiation | None = None
