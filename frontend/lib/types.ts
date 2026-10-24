// Mirrors backend/models.py. Keep the two in sync (TASKS.md 3.4): same field names, same literals.

export type Language = "en" | "kn" | "hi";
export type LocalBody = "municipal_corporation" | "city_municipal_council" | "other";
export type PremisesUse = "residential" | "non_residential";

export interface Facts {
  rent_per_month: number | null;
  deposit_inr: number | null;
  built_year: number | null;
  substantial_renovation_year: number | null;
  completion_month?: number | null; // asked only when the building turns 15 this year
  local_body: LocalBody | null;
  premises_use: PremisesUse;
  language: Language;
}

export interface Section {
  id: string; // e.g. "KRA-2(3)(e)", must exist in law/karnataka.json
  act: string;
  section: string;
  title: string;
  source_url: string;
  applies_in_karnataka: boolean;
}

export type Verdict = "cited" | "unverified" | "blocked";
export type TraceStepType =
  | "plan"
  | "question"
  | "tool_call"
  | "verifier"
  | "draft"
  | "approval"
  | "landlord_offer"
  | "tenant_decision"
  | "negotiation_settled"
  | "needs_itemisation";

// ---------- negotiation (identical to backend/models.py) ----------

/** The tenant's own limits: preferences, not legal limits. */
export interface TenantLimits {
  max_lock_in_months: number; // default 3
  refund_within_days: number; // default 30
  max_exit_painting_inr: number; // default 10000
}

export type LandlordPersona = "strict_owner" | "reasonable_broker";

export type Terms = Record<string, unknown>; // e.g. {"lock_in_months": 3}

export interface Offer {
  clause_id: string;
  move_id: string;
  text: string;
  terms: Terms;
}

export interface Decision {
  clause_id: string;
  decision: "accept" | "reject" | "counter";
  counter_terms: Terms | null;
  reason: string;
  section_id: string | null;
  verdict: Verdict;
  limit_override: boolean; // true when code flipped the model's accept to reject
}

export interface NegotiationRound {
  round: number;
  offers: Offer[];
  decisions: Decision[];
  model_ms: number;
  fallback: boolean;
}

export interface Negotiation {
  persona: LandlordPersona;
  limits: TenantLimits;
  rounds: NegotiationRound[];
  status: "running" | "settled" | "stalled";
  agreed_terms: Record<string, Terms>; // clause_id -> terms
  settled_clauses: string[];
  open_clauses: string[];
}

interface StepBase {
  index: number;
  at: string; // ISO timestamp
}

export interface PlanStep extends StepBase {
  type: "plan";
  steps: string[];
}

export interface QuestionStep extends StepBase {
  type: "question";
  field: keyof Facts;
  question: string;
  why: string;
  answer: string | null;
}

export interface ToolCallStep extends StepBase {
  type: "tool_call";
  tool: string;
  input: Record<string, unknown>;
  output: unknown;
  summary: string;
}

export interface VerifierStep extends StepBase {
  type: "verifier";
  claim: string;
  section_id: string | null;
  verdict: Verdict;
  reason: string;
}

export interface DraftStep extends StepBase {
  type: "draft";
  draft_id: string;
  tone: DraftTone;
}

export interface ApprovalStep extends StepBase {
  type: "approval";
  draft_id: string;
  approved: boolean;
  follow_up_date: string | null;
}

export interface LandlordOfferStep extends StepBase {
  type: "landlord_offer";
  round: number;
  persona: LandlordPersona;
  offers: Offer[];
}

export interface TenantDecisionStep extends StepBase {
  type: "tenant_decision";
  round: number;
  decisions: Decision[];
  model_ms: number;
  fallback: boolean;
  error: string | null; // why the round fell back to rules
}

export interface NegotiationSettledStep extends StepBase {
  type: "negotiation_settled";
  agreed_terms: Record<string, Terms>;
  settled_clauses: string[];
  open_clauses: string[];
}

export interface NeedsItemisationStep extends StepBase {
  type: "needs_itemisation";
  reason: string;
  withheld_inr: number;
  deposit_inr: number | null;
}

export type TraceStep =
  | PlanStep
  | QuestionStep
  | ToolCallStep
  | VerifierStep
  | DraftStep
  | ApprovalStep
  | LandlordOfferStep
  | TenantDecisionStep
  | NegotiationSettledStep
  | NeedsItemisationStep;

export type FindingCategory =
  | "deposit_forfeiture"
  | "lock_in"
  | "painting_or_cleaning_fixed"
  | "notice_shortfall"
  | "rent_escalation_excess";

export type Severity = "high" | "medium" | "low";

export interface Finding {
  clause_ref: string;
  clause_text: string;
  category: FindingCategory;
  issue: string;
  ask: string;
  section_ids: string[];
  money_at_risk_inr: number;
  money_note: string | null;
  severity: Severity;
}

export type DraftTone = "request" | "challenge" | "notice";

export interface Draft {
  id: string;
  tone: DraftTone;
  to: string;
  text: Partial<Record<Language, string>>; // the backend may return one language
  note: string | null; // draft_message's translation_note
}

// One reason from backend.tools.law.check_jurisdiction (docs/BACKEND_CONTRACT.md).
export type JurisdictionStatus = "excluded" | "needs_input" | "conditional";

export interface JurisdictionReason {
  section_id: string;
  status: JurisdictionStatus;
  text: string;
}

export interface GoverningLaw {
  rent_act_applies: boolean | null; // null: unresolved, never shown as excluded
  summary: string;
  section_ids: string[];
  reasons: JurisdictionReason[];
  missing: string[];
  note: string;
  governs: string[];
}

export type RunStatus = "running" | "needs_input" | "awaiting_approval" | "approved" | "failed" | "needs_itemisation";

export interface Run {
  id: string;
  task: string;
  title: string;
  status: RunStatus;
  created_at: string;
  model: string;
  facts: Facts;
  governing_law: GoverningLaw | null;
  trace: TraceStep[];
  findings: Finding[];
  drafts: Draft[];
  sections: Record<string, Section>;
  max_tool_calls: number;
  not_a_lawyer: true;
  notice: string;
  sample_note?: string | null; // stub mode only: facts the tenant entered that differ from the sample flat
  negotiation: Negotiation | null; // demo agreements only: the scripted landlord knows their clauses
}

export interface RunInput {
  text: string | null;
  file: File | null;
  facts: Facts;
  limits: TenantLimits;
  persona: LandlordPersona;
}

// Flow 2 (move-out): mirrors backend/agent/moveout.py through lib/backend.ts.
export type DeductionVerdict = "allowed" | "disputed";

export interface ChecklistEntry {
  id?: string; // E1, E2 ... referenced by a deduction's evidence_ids
  date: string;
  item: string;
  condition: string;
  evidence: string;
}

export interface Deduction {
  label: string;
  claimed_inr: number;
  verdict: DeductionVerdict | null; // null while the agent is still working
  reason: string;
  section_ids: string[];
  evidence_ids?: string[];
}

export interface MoveoutRun {
  id: string;
  title: string;
  status: RunStatus;
  facts: Facts;
  deposit_inr: number;
  checklist: ChecklistEntry[];
  deductions: Deduction[];
  next_steps: { title: string; detail: string; certainty: "established" | "uncertain" }[];
  sections: Record<string, Section>;
  drafts?: Draft[]; // the challenge, EN and KN (live only)
  follow_up_date?: string | null; // set once the tenant approves the challenge
  claimed_text?: string | null; // the landlord's message, when it was one number
  letter?: Partial<Record<Language, string>> | null; // needs_itemisation: the request for an itemised list
  itemisation?: NeedsItemisationStep | null;
  live?: boolean;
  not_a_lawyer: true;
  notice: string;
}

/** POST /api/moveout body (backend/models.py MoveoutRequest). */
export interface MoveoutInput {
  agreement_text: string;
  checklist: { id: string; date: string; item: string; condition: string; evidence: string }[];
  deductions: { clause_ref: string; category: string; label: string; amount_inr: number; evidence_ids: string[] }[];
  claimed_text?: string | null; // the landlord's message as sent, e.g. "painting and repairs 80396"
  facts: Record<string, unknown>;
  deposit_inr: number;
  language: Language;
}
