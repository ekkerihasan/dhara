// Single entry point for backend calls. With USE_STUBS on (the default until backend/main.py lands),
// every call is answered from stubs/*.json so the screens can be built and demoed without the API.

import blrFlat from "@/stubs/blr_flat.json";
import moveout from "@/stubs/moveout.json";
import { backendFacts, fromBackend, type BackendRun } from "./backend";
import { inr, LOCAL_BODY_LABEL } from "./format";
import type { ApprovalStep, Facts, Language, MoveoutRun, QuestionStep, Run, RunInput } from "./types";

export const USE_STUBS = process.env.NEXT_PUBLIC_USE_STUBS !== "false";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STUB_RUN_ID = "blr_flat";
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
function sampleNote(entered: Facts | null, sample: Facts): string | null {
  if (!entered) return null;
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
  run.sample_note = sampleNote(state.entered, run.facts);

  if (state.approvedAt) {
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

// ---------- public API ----------

export async function createRun(input: RunInput): Promise<string> {
  if (USE_STUBS) {
    await delay(400);
    writeState(STUB_RUN_ID, { ...DEFAULT_STATE, needsAnswer: input.facts.built_year === null, language: input.facts.language, entered: input.facts });
    return STUB_RUN_ID;
  }
  const run = await postJson<BackendRun>("/api/runs", {
    agreement_text: input.text,
    pdf_base64: input.file ? await toBase64(input.file) : null,
    facts: backendFacts(input.facts),
    language: input.facts.language,
  });
  saveFacts(run.id, input.facts);
  return run.id;
}

export async function getRun(id: string): Promise<Run> {
  if (USE_STUBS) {
    await delay(250);
    return stubRun(id);
  }
  const run = await request<BackendRun>(`/api/runs/${encodeURIComponent(id)}`);
  return fromBackend(run, loadFacts(id), "Your rental agreement");
}

export async function answerQuestion(id: string, field: keyof Facts, value: string): Promise<void> {
  if (USE_STUBS) {
    await delay(600);
    const state = readState(id);
    const entered = state.entered ? { ...state.entered, [field]: Number(value) || null } : null;
    writeState(id, { ...state, answer: value, entered });
    return;
  }
  const facts = { ...loadFacts(id), [field]: Number(value) || value };
  saveFacts(id, facts);
  await postJson(`/api/runs/${encodeURIComponent(id)}/answer`, { facts: { [field]: facts[field] } });
}

export async function approveDraft(id: string, draftId: string): Promise<void> {
  if (USE_STUBS) {
    await delay(400);
    writeState(id, { ...readState(id), approvedAt: new Date().toISOString() });
    return;
  }
  void draftId; // the backend approves the run's single draft
  await postJson(`/api/runs/${encodeURIComponent(id)}/approve`, { approved: true });
}

export async function getMoveout(id: string): Promise<MoveoutRun> {
  if (USE_STUBS) {
    await delay(250);
    if (id !== "moveout") throw new Error(`No stubbed move-out "${id}". Try /moveout/moveout.`);
    return structuredClone(moveout) as unknown as MoveoutRun;
  }
  return request<MoveoutRun>(`/api/moveout/${encodeURIComponent(id)}`);
}
