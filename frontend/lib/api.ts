// Single entry point for backend calls. With USE_STUBS on (the default until backend/main.py lands),
// every call is answered from stubs/*.json so the screens can be built and demoed without the API.

import blrFlat from "@/stubs/blr_flat.json";
import moveout from "@/stubs/moveout.json";
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

// ---------- stub state (per browser tab, so a refresh keeps the demo where it was) ----------

interface StubState {
  answer: string | null;
  needsAnswer: boolean;
  approvedAt: string | null;
  language: Language;
}

const DEFAULT_STATE: StubState = { answer: null, needsAnswer: false, approvedAt: null, language: "en" };

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
  if (state.answer) question.answer = state.answer;

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
    writeState(STUB_RUN_ID, { ...DEFAULT_STATE, needsAnswer: input.facts.built_year === null, language: input.facts.language });
    return STUB_RUN_ID;
  }
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.text) form.append("text", input.text);
  form.append("facts", JSON.stringify(input.facts));
  form.append("language", input.facts.language);
  const { id } = await request<{ id: string }>("/api/runs", { method: "POST", body: form });
  return id;
}

export async function getRun(id: string): Promise<Run> {
  if (USE_STUBS) {
    await delay(250);
    return stubRun(id);
  }
  return request<Run>(`/api/runs/${encodeURIComponent(id)}`);
}

export async function answerQuestion(id: string, field: keyof Facts, value: string): Promise<void> {
  if (USE_STUBS) {
    await delay(600);
    writeState(id, { ...readState(id), answer: value });
    return;
  }
  await postJson(`/api/runs/${encodeURIComponent(id)}/answer`, { field, value });
}

export async function approveDraft(id: string, draftId: string): Promise<void> {
  if (USE_STUBS) {
    await delay(400);
    writeState(id, { ...readState(id), approvedAt: new Date().toISOString() });
    return;
  }
  await postJson(`/api/runs/${encodeURIComponent(id)}/approve`, { draft_id: draftId });
}

export async function getMoveout(id: string): Promise<MoveoutRun> {
  if (USE_STUBS) {
    await delay(250);
    if (id !== "moveout") throw new Error(`No stubbed move-out "${id}". Try /moveout/moveout.`);
    return structuredClone(moveout) as unknown as MoveoutRun;
  }
  return request<MoveoutRun>(`/api/moveout/${encodeURIComponent(id)}`);
}
