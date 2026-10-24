// Mirrors backend/models.py. Keep the two in sync (TASKS.md 3.4): same field names, same literals.

export type Language = "en" | "kn";
export type LocalBody = "municipal_corporation" | "city_municipal_council" | "other";
export type PremisesUse = "residential" | "non_residential";

export interface Facts {
  rent_per_month: number | null;
  deposit_inr: number | null;
  built_year: number | null;
  substantial_renovation_year: number | null;
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
export type TraceStepType = "plan" | "question" | "tool_call" | "verifier" | "draft" | "approval";

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

export type TraceStep = PlanStep | QuestionStep | ToolCallStep | VerifierStep | DraftStep | ApprovalStep;

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
  text: Record<Language, string>;
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

export type RunStatus = "running" | "needs_input" | "awaiting_approval" | "approved" | "failed";

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
}

export interface RunInput {
  text: string | null;
  file: File | null;
  facts: Facts;
}

// Flow 2 (move-out). Placeholder shapes until backend/agent/moveout.py lands (TASKS.md 7.3).
export type DeductionVerdict = "allowed" | "disputed";

export interface ChecklistEntry {
  date: string;
  item: string;
  condition: string;
  evidence: string;
}

export interface Deduction {
  label: string;
  claimed_inr: number;
  verdict: DeductionVerdict;
  reason: string;
  section_ids: string[];
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
  not_a_lawyer: true;
  notice: string;
}
