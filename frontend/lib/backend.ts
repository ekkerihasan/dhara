// Converts the backend's RunResponse (backend/models.py) into the Run the screens render.
// The backend keeps a lean shape: generic {type, label, data} steps, no timestamps, one draft
// language, no facts or section metadata. Everything the screens need is derived here, in one place.

import type {
  ChecklistEntry,
  Deduction,
  Draft,
  DraftTone,
  Facts,
  Finding,
  FindingCategory,
  GoverningLaw,
  JurisdictionReason,
  Language,
  MoveoutRun,
  Run,
  RunStatus,
  Severity,
  TraceStep,
  TraceStepType,
  Verdict,
} from "./types";

export interface BackendStep {
  type: TraceStepType;
  label: string;
  data: Record<string, unknown>;
}

export interface BackendFinding {
  clause_ref: string;
  category: string;
  issue: string;
  ask?: string;
  clause_text?: string;
  money_at_risk_inr: number;
  section_ids: string[];
}

export interface BackendRun {
  id: string;
  status: "running" | "needs_input" | "ready" | "approved" | "failed";
  trace: BackendStep[];
  findings: BackendFinding[];
  drafts: { text: string; language: Language; tone: DraftTone; translation_note: string }[];
  question: string | null;
  approval: { follow_up_date?: string | null; delivery_status?: string } | null;
  notice: string;
  error: string | null;
}

/** The facts the backend's PropertyFacts accepts; it rejects any other field. */
export function backendFacts(facts: Facts) {
  const { rent_per_month, built_year, local_body, premises_use, substantial_renovation_year } = facts;
  return { rent_per_month, built_year, local_body, premises_use, substantial_renovation_year };
}

const STATUS: Record<BackendRun["status"], RunStatus> = {
  running: "running",
  needs_input: "needs_input",
  ready: "awaiting_approval",
  approved: "approved",
  failed: "failed",
};

const SEVERITY: Record<FindingCategory, Severity> = {
  deposit_forfeiture: "high",
  lock_in: "medium",
  painting_or_cleaning_fixed: "medium",
  notice_shortfall: "medium",
  rent_escalation_excess: "low",
};

const QUESTION: Partial<Record<keyof Facts, { question: string; why: string }>> = {
  built_year: {
    question: "In which year was the building constructed (or last substantially renovated)?",
    why: "Section 2(3)(f) of the Karnataka Rent Act exempts a building for 15 years after construction. I cannot decide which law governs without it.",
  },
  rent_per_month: { question: "What is the monthly rent?", why: "Section 2(3)(e) of the Karnataka Rent Act depends on the rent." },
  local_body: { question: "Which local body is the flat in?", why: "The Karnataka Rent Act applies only in the areas listed in its First Schedule." },
  premises_use: { question: "Is the flat used as a home?", why: "Section 2(3)(g) excludes most non-residential premises." },
};

const TOOL_NAMES = ["read_agreement", "check_jurisdiction", "lookup_section", "compute_money", "record_finding", "draft_message", "finish"];

const record = (v: unknown): Record<string, unknown> => (v && typeof v === "object" ? (v as Record<string, unknown>) : {});
const inr = (n: unknown) => `Rs ${Number(n).toLocaleString("en-IN")}`;

function lastJurisdiction(trace: BackendStep[]): Record<string, unknown> | null {
  const steps = trace.filter((s) => s.data.tool === "check_jurisdiction" && s.data.output);
  return steps.length ? record(steps[steps.length - 1].data.output) : null;
}

function governingLaw(trace: BackendStep[]): GoverningLaw | null {
  const j = lastJurisdiction(trace);
  if (!j) return null;
  const applies = (j.applies as boolean | null) ?? null;
  const reasons = (j.reasons as JurisdictionReason[]) ?? [];
  const excluded = reasons.filter((r) => r.status === "excluded").map((r) => r.section_id);
  const summary =
    applies === false
      ? "The Karnataka Rent Act, 1999 does not apply to this flat. The lease is governed by the agreement itself, read with the Transfer of Property Act, 1882 and the Indian Contract Act, 1872."
      : applies === true
        ? "The Karnataka Rent Act, 1999 applies to this flat, subject to the facts confirmed."
        : "Whether the Karnataka Rent Act, 1999 applies is unresolved: some facts are still missing.";
  return {
    rent_act_applies: applies,
    summary,
    section_ids: excluded,
    reasons,
    missing: (j.missing as string[]) ?? [],
    note: String(j.note ?? ""),
    governs: applies === false ? ["TPA-106", "TPA-108(m)", "ICA-74"] : [],
  };
}

function toolSummary(tool: string, data: Record<string, unknown>): string {
  const output = record(data.output);
  const input = record(data.inputs);
  if (data.error) return `${tool}: ${String(data.error)}`;
  switch (tool) {
    case "read_agreement": {
      const redactions = Object.values(record(output.redactions)).reduce<number>((sum, n) => sum + Number(n), 0);
      return `${String(output.clauses)} clauses read; ${redactions} personal identifiers redacted before any model call.`;
    }
    case "check_jurisdiction":
      return output.applies === false ? "Rent Act does not apply." : output.applies === true ? "Rent Act applies (conditional)." : "Rent Act coverage unresolved.";
    case "record_finding":
      return `${String(input.clause_ref)} ${String(input.category).replaceAll("_", " ")}: ${inr(output.money_at_risk_inr)}.`;
    case "compute_money":
      return `${String(input.finding_type).replaceAll("_", " ")}: ${inr(output.money_at_risk_inr)}.`;
    case "lookup_section":
      return data.output ? `${String(input.id)} found in the law pack.` : `${String(input.id)} is not in the law pack.`;
    case "draft_message":
      return `Draft written (${String(input.language)}, tone: ${String(input.tone)}).`;
    case "finish":
      return "Review complete; claims handed to the verifier.";
    default:
      return tool;
  }
}

function toStep(step: BackendStep, index: number, facts: Facts, seenPlan: boolean, pending: boolean): TraceStep | null {
  const base = { index, at: "" };
  const data = step.data;
  switch (step.type) {
    case "plan":
      return {
        ...base,
        type: "plan",
        steps: seenPlan
          ? ["Resume with the tenant's answer and rerun the Rent Act test."]
          : ((data.intended_tools as string[]) ?? []).map((t) => `Use ${t}.`),
      };
    case "question": {
      const field = (((data.missing as string[]) ?? [])[0] ?? "built_year") as keyof Facts;
      const text = QUESTION[field] ?? { question: String(data.question ?? step.label), why: "" };
      const value = facts[field];
      // Only the question the run is waiting on is unanswered; an earlier one with no value was "I don't know".
      const answer = value === null || value === undefined ? (pending ? null : "I don't know") : String(value);
      return { ...base, type: "question", field, ...text, answer };
    }
    case "tool_call": {
      const tool = String(data.tool ?? "");
      if (!TOOL_NAMES.includes(tool) && !data.error) return null; // e.g. "Jurisdiction selected" repeats the call above it
      return { ...base, type: "tool_call", tool: tool || step.label, input: record(data.inputs), output: data.output ?? data.error ?? null, summary: data.error ? step.label : toolSummary(tool, data) };
    }
    case "verifier": {
      const claim = record(data.claim);
      return { ...base, type: "verifier", claim: String(claim.text ?? ""), section_id: (claim.section_id as string | null) ?? null, verdict: claim.verdict as Verdict, reason: String(claim.reason ?? "") };
    }
    case "draft":
      return { ...base, type: "draft", draft_id: "d1", tone: (record(data.draft).tone as DraftTone) ?? "request" };
    case "approval": {
      const approval = record(data.approval);
      if (data.error) return { ...base, type: "tool_call", tool: "run", input: {}, output: data.error, summary: step.label };
      return { ...base, type: "approval", draft_id: "d1", approved: true, follow_up_date: (approval.follow_up_date as string | null) ?? null };
    }
  }
}

export function fromBackend(b: BackendRun, facts: Facts, title: string): Run {
  const trace: TraceStep[] = [];
  let seenPlan = false;
  for (const step of b.trace) {
    const pending = b.status === "needs_input" && step === b.trace.filter((s) => s.type === "question").at(-1);
    const converted = toStep(step, trace.length, facts, seenPlan, pending);
    if (step.type === "plan") seenPlan = true;
    if (converted) trace.push(converted);
  }
  const findings: Finding[] = b.findings.map((f) => ({
    clause_ref: f.clause_ref,
    clause_text: f.clause_text ?? "",
    category: f.category as FindingCategory,
    issue: f.issue,
    ask: f.ask ?? "",
    section_ids: f.section_ids,
    money_at_risk_inr: f.money_at_risk_inr,
    money_note: null,
    severity: SEVERITY[f.category as FindingCategory] ?? "medium",
  }));
  const drafts: Draft[] = b.drafts.length
    ? [{ id: "d1", tone: b.drafts[0].tone, to: "Landlord", text: Object.fromEntries(b.drafts.map((d) => [d.language, d.text])), note: b.drafts[0].translation_note }]
    : [];
  return {
    id: b.id,
    task: "live",
    title,
    status: STATUS[b.status],
    created_at: new Date().toISOString(),
    model: "live agent",
    facts,
    governing_law: governingLaw(b.trace),
    trace,
    findings,
    drafts,
    sections: {}, // the response carries ids only; chips link once the backend adds section metadata
    max_tool_calls: 12,
    not_a_lawyer: true,
    notice: b.notice,
  };
}

export interface BackendMoveout {
  id: string;
  status: BackendRun["status"];
  deductions: { id: string; label: string; amount_inr: number; verdict?: "allowed" | "disputed"; reason?: string; evidence_ids?: string[]; section_ids?: string[] }[];
  checklist: (ChecklistEntry & { id: string })[];
  drafts: BackendRun["drafts"];
  next_steps: MoveoutRun["next_steps"];
  approval: { follow_up_date?: string | null } | null;
  notice: string;
  error: string | null;
}

export function fromBackendMoveout(b: BackendMoveout, facts: Facts): MoveoutRun {
  const deductions: Deduction[] = b.deductions.map((d) => ({
    label: `${d.id} ${d.label.charAt(0).toUpperCase()}${d.label.slice(1)}`,
    claimed_inr: d.amount_inr,
    verdict: d.verdict ?? null,
    reason: d.reason ?? "",
    section_ids: d.section_ids ?? [],
    evidence_ids: d.evidence_ids ?? [],
  }));
  const drafts: Draft[] = b.drafts.length
    ? [{ id: "c1", tone: "challenge", to: "Landlord", text: Object.fromEntries(b.drafts.map((d) => [d.language, d.text])), note: b.drafts[0].translation_note }]
    : [];
  return {
    id: b.id,
    title: "Your move-out deductions",
    status: STATUS[b.status],
    facts,
    deposit_inr: facts.deposit_inr ?? 0,
    checklist: b.checklist,
    deductions,
    next_steps: b.next_steps,
    sections: {},
    drafts,
    follow_up_date: b.approval?.follow_up_date ?? null,
    live: true,
    not_a_lawyer: true,
    notice: b.notice,
  };
}
