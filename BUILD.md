# BUILD.md: phases, acceptance and commits

Times are IST, 24 to 25 Oct 2026. Hacking opens after the 10 AM talk. Checkpoints: 4 PM and 10 PM (online, both members present). Final deadline: plan for 10 AM 25 Oct until the organisers confirm otherwise.

Progress reporting to the mentor: come back at 25 percent (end of Phase 2), 50 percent (end of Phase 4, before checkpoint 1 prep), 75 percent (end of Phase 6, before checkpoint 2) and 100 percent (Phase 9). Bring: `git log --oneline`, test output, screenshots, and any blocker.

Owner key: H = Hasan (backend, Python), W = Wasih (frontend, TypeScript), B = both.

---

## Phase 0: baseline import (10:30 to 11:00) [B]

Goal: new repo `AbdulWasih05/dhara-tenancy` with the prototype as a clean first commit.

- Copy prototype excluding `.git`, `.venv`, `__pycache__`, `.pytest_cache`.
- `.gitignore` has `.env`, `.env.*`, `.venv/`, `__pycache__/`, `node_modules/`, `.next/`, `*.pyc`.
- `.env.example`: `GROQ_API_KEY=`, `SARVAM_API_KEY=`, `MODEL_PROVIDER=groq`, `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- Add CLAUDE.md, BUILD.md, TASKS.md.
- README rewritten per TASKS.md item 0.2 (Before and after, Note on prior work at the end).
- Run existing tests; record count.

Acceptance: `git check-ignore .env` prints `.env`; no secrets (`grep -rn "KEY=" .env.example` shows empty values); tests pass.

Commit: `chore: baseline import of Dhara AI offline prototype (April 2026, permitted by organisers)`

---

## Phase 1: law library and tools [H] and app scaffold [W] (11:00 to 13:00)

### 1H: statute library and two tools
- `law/karnataka.json`, 20+ entries (list in CLAUDE.md). Two entries with `applies_in_karnataka: false` for the Model Tenancy Act cap and Rent Authority.
- `backend/tools/law.py`: `lookup_section(id)`, `check_jurisdiction(rent_per_month, built_year, local_body, premises_use, substantial_renovation_year)` returning `{applies, reasons, missing}`. Reuse `housing/legal.py` logic by import.
- `tests/test_law.py`: 4 cases (Bengaluru 25000 built 2019 not applicable with KRA-2(3)(e) and KRA-2(3)(f); old building rent 3000 CMC applicable; missing built_year returns missing; MTA cap entry has applies_in_karnataka false).

Acceptance: pytest passes; printing `check_jurisdiction(25000, 2019, "municipal_corporation", "residential", None)` shows both reasons.

Commits:
- `feat(law): statute library with 20+ Karnataka, Registration, Contract and TPA sections`
- `feat(tools): check_jurisdiction and lookup_section with tests`

### 1W: Next.js scaffold and decision-trace screen on stubs
- `create-next-app` (TypeScript, Tailwind, App Router).
- Pages: `/` (upload PDF or paste text; facts form: rent, built year, local body type, use, language EN/KN), `/review/[id]` (decision trace + findings + approve), `/moveout/[id]` (placeholder).
- `components/Trace.tsx`: steps of type plan, question, tool_call (collapsible input/output JSON), verifier (claim, section id, verdict cited | unverified | blocked), draft, approval.
- `components/Findings.tsx`: clause text, issue, section id linked to source_url, money at risk in Rs, severity.
- `lib/types.ts` mirrors `backend/models.py`. `lib/api.ts` with `USE_STUBS`.
- `stubs/blr_flat.json`: a realistic full trace including one blocked claim about a 2-month cap.

Acceptance: `npm run build` passes; `/review/blr_flat` renders the trace with the blocked claim in red; works at 390 px width.

Commits:
- `feat(app): Next.js scaffold with upload and facts form`
- `feat(app): decision-trace and findings screens on stubbed blr_flat run`

**25 percent report after Phase 1.**

---

## Phase 2: verifier, scorer, three tasks [H] (13:00 to 15:30)

- `backend/agent/verifier.py`: takes a list of claims `{text, section_id|null}`; returns verdict per claim: `cited` if section_id exists and `applies_in_karnataka` is true; `blocked` if section exists but `applies_in_karnataka` is false (wrong law) or if a legal claim has no section_id; `unverified` for non-legal statements. A claim is "legal" if it matches a regex for Act, Section, s., law, legal, entitled, must, cap, limit.
- `env/tasks/blr_flat.json`, `pg_room.json`, `moveout.json`. Each: agreement text (synthetic, no real names), facts, expected `{governing_law, findings: [{clause_ref, category, money_at_risk_inr, expected_sections}], forbidden_sections}`. `pg_room` includes 3 scripted landlord pushback messages. `moveout` includes a move-in checklist with dated entries and 3 claimed deductions (painting 15000, cleaning 5000, "wear and tear" 8000).
- `env/scorer.py`: `score(task, run) -> {governing_law_correct: 0|1, money_within_500: fraction, citations_exist: fraction, wrong_law_penalty: -1 per forbidden section cited, total}`.
- `tests/test_scorer.py`: a perfect run scores max; a run citing MTA cap gets the penalty; money off by 600 fails that check.

Acceptance: `python -m env.scorer env/tasks/blr_flat.json env/tasks/sample_run.json` prints a score table; tests pass.

Commits:
- `feat(verifier): block uncited and wrong-law claims`
- `feat(env): blr_flat, pg_room and moveout tasks`
- `feat(scoring): governing-law, money-at-risk and citation checks with wrong-law penalty`

---

## Phase 3: remaining tools and PII redaction [H] (14:30 to 15:45, overlaps Phase 2 tail)

- `backend/tools/agreement.py`: `read_agreement(pdf_bytes|text) -> {clauses: [{id, text, page}]}` using pypdf; PII redaction before return (regexes in CLAUDE.md), with a count of redactions.
- `backend/tools/money.py`: `compute_money(finding_type, inputs) -> int` using CLAUDE.md formulas.
- `backend/tools/messages.py`: `draft_message(findings, tone: request|challenge|notice, language: en|kn)` using the prototype templates in `housing/messages.py` where they fit; `send_and_schedule(message, approved: bool)` which refuses unless approved and records a follow-up date (+7 days) in memory.
- Tests for each.

Commits:
- `feat(tools): read_agreement with PII redaction, compute_money, draft_message`
- `feat(tools): send_and_schedule with approval gate`

---

## Phase 4: checkpoint 1 prep (15:30 to 16:00) [B]

Both stop coding at 15:40. README Status section updated with ticks. One terminal window ready with: pytest run, scorer run on a sample showing the penalty, `check_jurisdiction` call. Browser tab on `/review/blr_flat` (stubbed). Order of showing and who speaks: TASKS.md section "Checkpoint roles".

Commit: `docs: README progress for checkpoint 1`

**50 percent report before 16:00.** Checkpoint 1 at 16:00.

---

## Phase 5: tenant agent loop and API [H] (16:30 to 20:00)

- `backend/llm/provider.py`: `chat(messages, tools)` for Groq (OpenAI-compatible tool calling) and Sarvam if it passed the test. Retries once; 30 s timeout.
- `backend/agent/tenant.py`: loop per CLAUDE.md agent contract. Tools registered as JSON schemas. Every step appended to trace. Missing jurisdiction inputs produce a `question` step and the run pauses with status `needs_input`.
- `backend/main.py`: `POST /api/runs` (text or PDF + facts + language) returns run id; `GET /api/runs/{id}` returns status, trace, findings, drafts; `POST /api/runs/{id}/answer` for questions; `POST /api/runs/{id}/approve`. CORS for localhost:3000.
- Baseline mode: `POST /api/runs?mode=baseline` sends the same agreement to the model with no tools and parses the text into claims for the verifier and scorer.

Acceptance: a curl run of blr_flat completes with trace containing plan, 1 question or 0, at least 3 tool_calls, verifier verdicts, 1 draft; `pytest` passes; a fake-provider test runs the loop without network.

Commits:
- `feat(llm): provider with tool calling and retry`
- `feat(agent): tenant agent loop with planning, tool dispatch and trace`
- `feat(api): runs, answer and approve endpoints`

## Phase 6: wire frontend to API, Kannada [W] (16:30 to 21:30)

- Replace stubs with live API; poll `GET /api/runs/{id}` every 1.5 s; render `needs_input` as a question card with an inline answer form.
- Approve button calls `/approve`; show the scheduled follow-up date.
- Language toggle EN/KN; drafts shown in chosen language (backend provides both).
- Empty, loading and error states. Not-a-lawyer notice in the footer.
- `docs/screenshots/` with 3 PNGs for the README.

Acceptance: Flow 1 end to end in the browser on blr_flat with a real model call; Kannada draft visible.

Commits:
- `feat(app): live runs with question cards and approve-to-send`
- `feat(i18n): Kannada drafts in review screen`
- `docs: README progress for checkpoint 2`

**75 percent report by 21:40.** Checkpoint 2 at 22:00. Both stop coding at 21:40.

---

## Phase 7: scoring run and fixes [H], Flow 2 screen [W] (22:30 to 02:00)

- `env/run_eval.py`: runs each task twice (baseline, agent), scores both, writes `env/results/scores.md` and `scores.json`. Commit the results. Fix the biggest agent failure and rerun.
- `backend/agent/moveout.py` and `POST /api/moveout`: input claimed deductions; compare against agreement clauses and the move-in checklist; per deduction: allowed | disputed with reason and section; drafts a challenge, and a firmer notice on second call; ends with "next formal step" per CLAUDE.md recovery routes.
- Frontend `/moveout/[id]`: deductions table, verdict per row, draft, approve.

Commits:
- `feat(eval): baseline vs agent runner`
- `chore(eval): first scores table`
- `fix(agent): <biggest failure from the scoring run>`
- `feat(moveout): Flow 2 for claimed deductions with next formal step`
- `feat(app): move-out screen`

---

## Phase 8: stretch, only after Phase 7 is green (02:00 to 07:00)

In order: model-driven landlord agent for pg_room (replaces scripted pushback), Hindi drafts via prototype templates, public-chatbot side test (10 questions, results table in README), Sarvam voice input, photo OCR via Sarvam Vision, locality chart.

Each stretch item: its own commit, its own README line.

---

## Phase 9: ship (07:00 to 09:30) [B]

- README final: setup, architecture diagram (Mermaid), scores table at the top, credits, responsible AI, Before and after with all ticks, Note on prior work at the end.
- Demo video 3 to 4 minutes (script in TASKS.md), link in README.
- `git log -p | grep -iE "api[_-]?key\s*=\s*['\"]?[A-Za-z0-9]{12,}"` returns nothing.
- Final push by 09:30. Stop pushing at the deadline.

Commits:
- `docs: full README (setup, architecture, scores, credits, responsible AI)`
- `docs: demo video link and screenshots`
- `chore: final cleanup, verify no secrets in history`

**100 percent report at 09:30.**
