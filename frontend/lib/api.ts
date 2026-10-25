// Single entry point for backend calls. With USE_STUBS on (the default until backend/main.py lands),
// every call is answered from stubs/*.json so the screens can be built and demoed without the API.

import blrFlat from "@/stubs/blr_flat.json";
import blrNegotiation from "@/stubs/blr_flat_negotiation.json";
import moveout from "@/stubs/moveout.json";
import moveoutItemisation from "@/stubs/moveout_itemisation.json";
import { backendFacts, fromBackend, fromBackendMoveout, type BackendMoveout, type BackendRun } from "./backend";
import { inr, LOCAL_BODY_LABEL } from "./format";
import type { ApprovalStep, Facts, Language, MoveoutInput, MoveoutRun, Negotiation, QuestionStep, Run, RunInput, TraceStep } from "./types";

export const USE_STUBS = process.env.NEXT_PUBLIC_USE_STUBS !== "false";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STUB_RUN_ID = "blr_flat";
const STUB_MOVEOUT_ID = "moveout";
const STUB_ITEMISATION_ID = "moveout_itemisation";
const STUB_ROUND_MS = 1800; // the sample negotiation fills in one round at a time after a review starts

/** The sample runs (top-bar links) always come from the stubs, even when the live API is on. */
const isSample = (id: string) => USE_STUBS || id === STUB_RUN_ID || id === STUB_MOVEOUT_ID || id === STUB_ITEMISATION_ID;
const FOLLOW_UP_DAYS = 7;

// ---------- live API (BUILD.md Phase 5 endpoints) ----------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

// The backend does not echo facts back, so the browser keeps what the tenant entered, per run.
const EMPTY_FACTS: Facts = { rent_per_month: null, deposit_inr: null, built_year: null, substantial_renovation_year: null, local_body: null, premises_use: "residential", language: "en" };

function saveFacts(id: string, facts: Facts): void {
  try {
    sessionStorage.setItem(`dhara:facts:${id}`, JSON.stringify(facts));
  } catch {
    // storage blocked: the report still renders, without the facts strip
  }
}

function loadFacts(id: string): Facts {
  try {
    const raw = sessionStorage.getItem(`dhara:facts:${id}`);
    return raw ? { ...EMPTY_FACTS, ...(JSON.parse(raw) as Partial<Facts>) } : EMPTY_FACTS;
  } catch {
    return EMPTY_FACTS;
  }
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

// ---------- stub state (per browser tab, so a refresh keeps the demo where it was) ----------

interface StubState {
  answer: string | null;
  needsAnswer: boolean;
  approvedAt: string | null;
  language: Language;
  entered: Facts | null; // what the tenant typed, compared with the sample flat
  unknown?: string[]; // facts answered "I don't know"
  readyAt?: string | null; // when the findings were ready; the sample negotiation runs from here
  persona?: string; // the landlord style the tenant picked
}

const DEFAULT_STATE: StubState = { answer: null, needsAnswer: false, approvedAt: null, language: "en", entered: null };

function readState(id: string): StubState {
  try {
    const raw = sessionStorage.getItem(`dhara:stub:${id}`);
    return raw ? { ...DEFAULT_STATE, ...(JSON.parse(raw) as Partial<StubState>) } : DEFAULT_STATE;
  } catch {
    return DEFAULT_STATE;
  }
}

function writeState(id: string, state: StubState): void {
  try {
    sessionStorage.setItem(`dhara:stub:${id}`, JSON.stringify(state));
  } catch {
    // storage blocked: the demo still works, it just forgets on refresh
  }
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

/** The stub is precomputed for one sample flat. Name every fact the tenant entered that differs from it. */
function sampleNote(entered: Facts | null, sample: Facts, unknown: string[] = []): string | null {
  if (!entered) return null;
  if (unknown.includes("built_year")) return `You answered "I don't know" for the built year; the sample was computed for a building from ${sample.built_year}, and a live review marks the Rent Act result unresolved.`;
  const show = {
    rent_per_month: (v: number | null) => (v === null ? "blank" : `${inr(v)}/month`),
    deposit_inr: (v: number | null) => (v === null ? "blank" : inr(v)),
    built_year: (v: number | null) => (v === null ? "blank" : String(v)),
    substantial_renovation_year: (v: number | null) => (v === null ? "none" : String(v)),
  };
  const LABEL = { rent_per_month: "rent", deposit_inr: "deposit", built_year: "built year", substantial_renovation_year: "renovation year" };
  const diffs: string[] = [];
  for (const key of Object.keys(show) as (keyof typeof show)[]) {
    if (entered[key] !== null && entered[key] !== sample[key]) diffs.push(`${LABEL[key]} ${show[key](entered[key])} (sample: ${show[key](sample[key])})`);
  }
  if (entered.local_body && entered.local_body !== sample.local_body)
    diffs.push(`local body ${LOCAL_BODY_LABEL[entered.local_body]} (sample: ${sample.local_body ? LOCAL_BODY_LABEL[sample.local_body] : "blank"})`);
  if (entered.premises_use !== sample.premises_use) diffs.push(`use ${entered.premises_use.replace("_", "-")} (sample: ${sample.premises_use})`);
  return diffs.length ? `You entered ${diffs.join(", ")}.` : null;
}

/** The trace steps the backend appends for a negotiation, rebuilt from the Negotiation itself. */
function negotiationSteps(negotiation: Negotiation, start: number): TraceStep[] {
  const steps: TraceStep[] = [];
  for (const r of negotiation.rounds) {
    steps.push({ index: start + steps.length, at: "", type: "landlord_offer", round: r.round, persona: negotiation.persona, offers: r.offers });
    steps.push({ index: start + steps.length, at: "", type: "tenant_decision", round: r.round, decisions: r.decisions, model_ms: r.model_ms, fallback: r.fallback, error: null });
  }
  if (negotiation.status !== "running") {
    const { agreed_terms, settled_clauses, open_clauses } = negotiation;
    steps.push({ index: start + steps.length, at: "", type: "negotiation_settled", agreed_terms, settled_clauses, open_clauses });
  }
  return steps;
}

/** The sample negotiation, as far as it has got: round 1 first, then round 2 and the outcome. */
function stubNegotiation(readyAt: string | null | undefined): Negotiation {
  const full = structuredClone(blrNegotiation) as unknown as Negotiation & { agreed_letter?: unknown };
  delete full.agreed_letter;
  const elapsed = readyAt ? Date.now() - new Date(readyAt).getTime() : Infinity;
  const rounds = Math.min(full.rounds.length, Math.floor(elapsed / STUB_ROUND_MS));
  if (rounds >= full.rounds.length) return full;
  return { ...full, rounds: full.rounds.slice(0, rounds), status: "running", agreed_terms: {}, settled_clauses: [], open_clauses: [] };
}

function stubRun(id: string): Run {
  if (id !== STUB_RUN_ID) throw new Error(`No stubbed run "${id}". Try /review/${STUB_RUN_ID}.`);
  const run = structuredClone(blrFlat) as unknown as Run;
  const state = readState(id);
  run.facts.language = state.language;

  const qIndex = run.trace.findIndex((s) => s.type === "question");
  const question = run.trace[qIndex] as QuestionStep;

  // Built year left blank on the form: the agent stops at its question and waits.
  if (state.needsAnswer && !state.answer) {
    question.answer = null;
    return { ...run, facts: { ...run.facts, built_year: null }, status: "needs_input", trace: run.trace.slice(0, qIndex + 1), governing_law: null, findings: [], drafts: [] };
  }
  // The trace keeps the sample's own answer so it matches the tool calls below it; sample_note names the difference.
  run.sample_note = sampleNote(state.entered, run.facts, state.unknown);
  if (state.persona === "reasonable_broker")
    run.sample_note = `${run.sample_note ?? ""} You chose a reasonable broker; the sample negotiation is against a strict owner.`.trim();

  if (!state.readyAt && state.entered) writeState(id, { ...state, readyAt: new Date().toISOString() });
  run.negotiation = stubNegotiation(state.approvedAt ? null : (readyAt(id) ?? null));
  run.trace.push(...negotiationSteps(run.negotiation, run.trace.length));

  if (state.approvedAt) {
    run.drafts = [{ ...run.drafts[0], text: blrNegotiation.agreed_letter, note: run.drafts[0].note }];
    const approval: ApprovalStep = {
      index: run.trace.length,
      type: "approval",
      at: state.approvedAt,
      draft_id: run.drafts[0].id,
      approved: true,
      follow_up_date: addDays(state.approvedAt, FOLLOW_UP_DAYS),
    };
    run.trace.push(approval);
    run.status = "approved";
  }
  return run;
}

function readyAt(id: string): string | null | undefined {
  return readState(id).readyAt;
}

// ---------- public API ----------

export async function createRun(input: RunInput): Promise<string> {
  if (USE_STUBS) {
    await delay(400);
    writeState(STUB_RUN_ID, { ...DEFAULT_STATE, needsAnswer: input.facts.built_year === null, language: input.facts.language, entered: input.facts, persona: input.persona });
    return STUB_RUN_ID;
  }
  const run = await postJson<BackendRun>("/api/runs", {
    agreement_text: input.text,
    pdf_base64: input.file ? await toBase64(input.file) : null,
    facts: backendFacts(input.facts),
    language: input.facts.language,
    limits: input.limits,
    persona: input.persona,
  });
  saveFacts(run.id, input.facts);
  return run.id;
}

export async function getRun(id: string): Promise<Run> {
  if (isSample(id)) {
    await delay(250);
    return stubRun(id);
  }
  const run = await request<BackendRun>(`/api/runs/${encodeURIComponent(id)}`);
  return fromBackend(run, loadFacts(id), "Your rental agreement");
}

export async function answerQuestion(id: string, field: keyof Facts, value: string): Promise<void> {
  if (isSample(id)) {
    await delay(600);
    const state = readState(id);
    const entered = state.entered ? { ...state.entered, [field]: Number(value) || null } : null;
    const unknown = value === "" ? [...(state.unknown ?? []), field] : state.unknown; // "" = I don't know
    writeState(id, { ...state, answer: value || "unknown", entered, unknown, readyAt: new Date().toISOString() });
    return;
  }
  const facts = { ...loadFacts(id), [field]: value === "" ? null : Number(value) || value }; // "" = I don't know
  saveFacts(id, facts);
  await postJson(`/api/runs/${encodeURIComponent(id)}/answer`, { facts: { [field]: facts[field] } });
}

/** Approve the run's draft; with a negotiation, the agreed terms the tenant saw (the backend rewrites the letter from them). */
export async function approveDraft(id: string, draftId: string, agreedTerms: Negotiation["agreed_terms"] | null = null): Promise<void> {
  if (isSample(id)) {
    await delay(400);
    writeState(id, { ...readState(id), approvedAt: new Date().toISOString() });
    return;
  }
  void draftId; // the backend approves the run's single draft
  await postJson(`/api/runs/${encodeURIComponent(id)}/approve`, agreedTerms ? { approved: true, agreed_terms: agreedTerms } : { approved: true });
}

export async function createMoveout(input: MoveoutInput): Promise<string> {
  const lumpSum = !input.deductions.length;
  if (USE_STUBS) {
    await delay(400);
    saveMoveoutInput(lumpSum ? STUB_ITEMISATION_ID : STUB_MOVEOUT_ID, input);
    return lumpSum ? STUB_ITEMISATION_ID : STUB_MOVEOUT_ID;
  }
  const review = await postJson<BackendMoveout>("/api/moveout", input);
  saveFacts(review.id, { ...EMPTY_FACTS, ...(input.facts as Partial<Facts>), deposit_inr: input.deposit_inr, language: input.language });
  saveMoveoutInput(review.id, input);
  return review.id;
}

// The itemised resubmission reuses the agreement, checklist and facts of the first request.
function saveMoveoutInput(id: string, input: MoveoutInput): void {
  try {
    sessionStorage.setItem(`dhara:moveout:${id}`, JSON.stringify(input));
  } catch {
    // storage blocked: the resubmit form falls back to the sample request
  }
}

export function loadMoveoutInput(id: string): MoveoutInput | null {
  try {
    const raw = sessionStorage.getItem(`dhara:moveout:${id}`);
    return raw ? (JSON.parse(raw) as MoveoutInput) : null;
  } catch {
    return null;
  }
}

export async function getMoveout(id: string): Promise<MoveoutRun> {
  if (isSample(id)) {
    await delay(250);
    if (id === STUB_ITEMISATION_ID) return structuredClone(moveoutItemisation) as unknown as MoveoutRun;
    if (id !== STUB_MOVEOUT_ID) throw new Error(`No stubbed move-out "${id}". Try /moveout/moveout.`);
    return structuredClone(moveout) as unknown as MoveoutRun;
  }
  return fromBackendMoveout(await request<BackendMoveout>(`/api/moveout/${encodeURIComponent(id)}`), loadFacts(id));
}

export async function approveMoveout(id: string): Promise<void> {
  if (isSample(id)) return;
  await postJson(`/api/moveout/${encodeURIComponent(id)}/approve`, { approved: true });
}

/** Speech to facts (live only): the backend transcribes the recording and returns checked form fields. */
export async function voiceFacts(audio: Blob, language: Language): Promise<{ transcript: string; facts: Partial<Facts> }> {
  const form = new FormData();
  form.append("audio", audio, "speech.webm");
  form.append("language", language);
  return request<{ transcript: string; facts: Partial<Facts> }>("/api/voice", { method: "POST", body: form });
}
