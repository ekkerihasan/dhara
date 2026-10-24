"""Pydantic schemas shared by the backend API and the frontend handoff."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Language = Literal["en", "kn"]
RunStatus = Literal["running", "needs_input", "ready", "approved", "failed"]
TraceType = Literal["plan", "question", "tool_call", "verifier", "draft", "approval"]


class PropertyFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rent_per_month: float | None = Field(default=None, ge=0)
    built_year: int | None = Field(default=None, ge=1)
    local_body: str | None = None
    premises_use: str | None = None
    substantial_renovation_year: int | None = Field(default=None, ge=1)
    standard_rent_monthly: float | None = Field(default=None, ge=0)
    ownership_type: str | None = None
    other_exemptions_checked: bool | None = None
    tenancy_date: str | None = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreement_text: str | None = None
    pdf_base64: str | None = None
    facts: PropertyFacts = Field(default_factory=PropertyFacts)
    language: Language = "en"


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
    model_config = ConfigDict(extra="forbid")

    agreement_text: str
    checklist: list[ChecklistEntry] = Field(default_factory=list)
    deductions: list[ClaimedDeduction] = Field(min_length=1)
    facts: PropertyFacts = Field(default_factory=PropertyFacts)
    language: Language = "en"


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


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
    mode: Literal["agent", "baseline"] = "agent"
    baseline_output: dict[str, Any] | None = None
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
