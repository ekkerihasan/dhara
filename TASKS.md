# TASKS.md: who does what, in order

Tick a box only when the acceptance check in BUILD.md passes and the commit is pushed. Report to the mentor at 25, 50, 75 and 100 percent (marked below).

Owner key: H = Hasan (backend, Python), W = Wasih (frontend, TypeScript), B = both.

## Pre-event (23 Oct night)

- [x] 0.A [B] Throwaway tool-calling test: Sarvam-105B vs Groq llama-3.3-70b-versatile. Not committed. Record the verdict here: Sarvam: ____ Groq: ____ Chosen: ____
- [x] 0.B [B] Both have Groq and Sarvam keys in a local `.env` (never committed). Both can push to `AbdulWasih05/dhara-tenancy` under their own git identity.
- [x] 0.C [W] Node 20+, `npx create-next-app` cached. [H] Python 3.11 venv with fastapi, uvicorn, pydantic, httpx, pypdf, pytest installed.
- [x] 0.D [B] Organiser confirmation screenshot saved outside the repo.
- [x] 0.E [B] Sleep. Night shift decided: ____ takes 02:00 to 06:00.

## Phase 0 (10:30 to 11:00)

- [x] 0.1 [W] New repo, baseline import, `.gitignore`, `.env.example`, CLAUDE.md, BUILD.md, TASKS.md. Commit: `chore: baseline import of Dhara AI offline prototype (April 2026, permitted by organisers)`
- [x] 0.2 [H] README rewrite: title, one-liner, track and theme line, "Before and after" two-column section (existed before: offline rules-based Karnataka screening, clause extraction, EN/KN/HI templates, scripted counterparty, local OCR, OpenEnv tasks, tests, no model; built at ChronoForge: empty checklist), old notes moved under "Original prototype notes", and "Note on prior work" as the last section stating organiser permission and that every checklist item was written during the event. Included in 0.1's commit or `docs: README before/after and note on prior work`.
- [x] 0.3 [H] Existing tests run; count recorded in README Status.

## Phase 1 (11:00 to 13:00)

- [ ] 1.1 [H] `law/karnataka.json` 20+ entries. Commit: `feat(law): statute library with 20+ Karnataka, Registration, Contract and TPA sections`
- [ ] 1.2 [H] `backend/tools/law.py` + `tests/test_law.py`. Commit: `feat(tools): check_jurisdiction and lookup_section with tests`
- [x] 1.3 [W] Next.js scaffold, `/` page with upload and facts form. Commit: `feat(app): Next.js scaffold with upload and facts form`
- [x] 1.4 [W] Trace and Findings components, `/review/[id]` on `stubs/blr_flat.json`, types in `lib/types.ts`. Commit: `feat(app): decision-trace and findings screens on stubbed blr_flat run`

**REPORT 25 percent** (bring `git log --oneline`, pytest output, screenshot of `/review/blr_flat`).

## Phase 2 and 3 (13:00 to 15:45)

- [ ] 2.1 [H] Verifier + tests. Commit: `feat(verifier): block uncited and wrong-law claims`
- [ ] 2.2 [H] Three task files. Commit: `feat(env): blr_flat, pg_room and moveout tasks`
- [ ] 2.3 [H] Scorer + tests. Commit: `feat(scoring): governing-law, money-at-risk and citation checks with wrong-law penalty`
- [ ] 3.1 [H] read_agreement (pypdf + PII redaction), compute_money, draft_message. Commit: `feat(tools): read_agreement with PII redaction, compute_money, draft_message`
- [ ] 3.2 [H] send_and_schedule with approval gate. Commit: `feat(tools): send_and_schedule with approval gate`
- [x] 3.3 [W] `/moveout/[id]` placeholder on a stub; question card component for `needs_input`; mobile pass. Commit: `feat(app): question card, move-out placeholder, mobile layout`
- [ ] 3.4 [W] Keep `lib/types.ts` in sync with `backend/models.py` as Hasan adds fields (coordinate on a shared `models.py` draft by 14:00).

## Phase 4: checkpoint 1 (15:30 to 16:00) [B]

- [ ] 4.1 [B] Stop coding 15:40. README Status ticks. Commit: `docs: README progress for checkpoint 1`
- [ ] 4.2 [H] Terminal ready: `pytest -q`; `python -m env.scorer env/tasks/blr_flat.json env/tasks/sample_run_wronglaw.json` showing the penalty; `check_jurisdiction` one-liner.
- [x] 4.3 [W] Browser ready: `/review/blr_flat` stubbed, blocked claim in red.

**REPORT 50 percent** (before 16:00).

## Phase 5 and 6 (16:30 to 21:40)

- [ ] 5.1 [H] `backend/llm/provider.py`. Commit: `feat(llm): provider with tool calling and retry`
- [ ] 5.2 [H] `backend/agent/tenant.py` + fake-provider test. Commit: `feat(agent): tenant agent loop with planning, tool dispatch and trace`
- [ ] 5.3 [H] `backend/main.py` endpoints + baseline mode. Commit: `feat(api): runs, answer and approve endpoints`
- [ ] 6.1 [W] Live API, polling, question cards, approve with follow-up date. Commit: `feat(app): live runs with question cards and approve-to-send`
- [ ] 6.2 [W] EN/KN toggle, Kannada drafts. Commit: `feat(i18n): Kannada drafts in review screen`
- [ ] 6.3 [W] 3 screenshots in `docs/screenshots/`; README Status ticks. Commit: `docs: README progress for checkpoint 2`

**REPORT 75 percent** (by 21:40). Checkpoint 2 at 22:00. Both stop coding at 21:40.

## Phase 7 (22:30 to 02:00)

- [ ] 7.1 [H] `env/run_eval.py`, scores committed. Commits: `feat(eval): baseline vs agent runner`, `chore(eval): first scores table`
- [ ] 7.2 [H] Fix biggest failure, rerun. Commit: `fix(agent): <what it was>`
- [ ] 7.3 [H] Flow 2 backend with "next formal step". Commit: `feat(moveout): Flow 2 for claimed deductions with next formal step`
- [ ] 7.4 [W] Move-out screen. Commit: `feat(app): move-out screen`
- [ ] 7.5 [W] Scores table rendered at the top of README from `env/results/scores.md`. Commit: `docs: scores table in README`

## Phase 8: stretch (02:00 to 07:00), in this order, each its own commit

- [ ] 8.1 [H] Model-driven landlord agent for pg_room. `feat(landlord): model-driven landlord agent for negotiation`
- [ ] 8.2 [W] Hindi drafts. `feat(i18n): Hindi drafts`
- [ ] 8.3 [H] Public-chatbot side test, 10 questions, table in README. `docs(eval): public chatbot wrong-law test`
- [ ] 8.4 [W] Sarvam voice input (Saaras) on the facts form. `feat(voice): speak the terms`
- [ ] 8.5 [H] Photo OCR via Sarvam Vision. `feat(ocr): photo agreements`
- [ ] 8.6 [W] Locality chart of disputed clause types from the three tasks. `feat(app): locality chart`

## Phase 9: ship (07:00 to 09:30)

- [ ] 9.1 [H] README final (setup, Mermaid architecture, scores at top, credits, responsible AI, before/after ticks, note on prior work last). `docs: full README (setup, architecture, scores, credits, responsible AI)`
- [ ] 9.2 [W] Demo video recorded and linked. `docs: demo video link and screenshots`
- [ ] 9.3 [B] Secrets check on full history, final push by 09:30. `chore: final cleanup, verify no secrets in history`

**REPORT 100 percent** at 09:30.

---

## Checkpoint roles (both present, online, screen share)

Checkpoint 1 (16:00), 5 minutes:
1. Wasih (30 s): one-line problem, one-line what Dhara does, "we are building the agent on top of our rules-based prototype; here is what is new today".
2. Hasan shares terminal (2 min): pytest; scorer run showing the wrong-law penalty firing on the 2-month cap; `check_jurisdiction(25000, 2019, ...)` returning not applicable with s.2(3)(e) and (f).
3. Wasih shares browser (1.5 min): `/review/blr_flat` trace with the blocked claim; explains the plan, question, tool_call, verifier steps.
4. Hasan (30 s): next 6 hours: agent loop, live API, Kannada.
Judges will probe: why agentic and not a prompt (answer: planning step, missing-input questions, tool calls, verifier gate, all in the trace); how do you know the section exists (answer: lookup against law/karnataka.json with India Code links; anything else is blocked); what if the model fails (answer: Groq fallback, and the verifier and scorer do not depend on the model).

Checkpoint 2 (22:00), 5 minutes:
1. Wasih drives the browser: upload blr_flat PDF, facts form with built year left blank, agent asks for it, answer, trace fills, findings with money at risk, Kannada draft, approve, follow-up scheduled.
2. Hasan shows the terminal: the same run in baseline mode and its verifier verdicts, to preview the scoring comparison.
3. Both: next 12 hours: scores, Flow 2, stretch.
Judges will probe: is the money number real (answer: deterministic formulas in CLAUDE.md, scorer tolerance Rs 500); what does the tenant actually get (answer: a counter-proposal they approve, a move-in checklist, and at move-out a challenge with a next formal step); scale (answer: law pack is a JSON file per state; same agents).

Final (confirm time), 7 to 8 minutes: problem (1 min, Wasih), what is new vs the prototype (30 s, Hasan), live demo Flow 1 then Flow 2 (3 min, Wasih drives, Hasan narrates the trace), scores table baseline vs agent and the chatbot side test (1.5 min, Hasan), impact and scale (1 min, Wasih), questions.

## Demo video script (3 to 4 minutes, record at 07:30)

0:00 Title card. "Dhara AI: Agentic Tenancy Copilot for Fair Renting. Built at ChronoForge 2026."
0:10 Problem in two sentences over a screenshot of a Bengaluru deposit news headline: deposits of 6 to 9 months, deductions argued over WhatsApp, viral posts citing a 2-month cap that does not apply in Karnataka.
0:35 Upload the blr_flat agreement, fill rent and local body, leave built year blank.
0:50 The agent plans, asks for the built year. Answer it. Narrate: "it needed this to run the Rent Act test".
1:10 Trace fills: check_jurisdiction (not applicable, s.2(3)(e) and (f)), lookup_section calls, verifier blocks a 2-month cap claim in red. Narrate: "the verifier refused a claim the public chatbots make".
1:40 Findings with money at risk; Kannada draft; approve; follow-up date.
2:10 Move-out: enter three claimed deductions; agent allows one, disputes two against the move-in checklist; drafts the challenge; shows the next formal step.
2:50 Scores table: baseline vs agent per task; the wrong-law penalty count; chatbot side test.
3:20 "Each state is a law pack. Same agents." Credits and not-a-lawyer notice.

## Current checkout progress

Phase 0 complete (Hasan): baseline import `7132cfa` (`chore: initialize Dhara AI project`) and TASKS update `32afffc`, pushed to master of https://github.com/ekkerihasan/dhara (team repo; replaces `AbdulWasih05/dhara-tenancy` in 0.B). Validation: 51 tests and 6 subtests passed using the earlier project's Python 3.10.11 environment; ignore rules, empty API-key placeholders and staged secret check passed. Python 3.11 setup remains pending.

Phase 1 not started: no `law/`, `backend/`, `env/` or `frontend/` yet. Next for H: 1.1, 1.2.

Frontend (Wasih): 1.3, 1.4 and 3.3 done on stubs in `frontend/` (`npm run build` and `npm run lint` pass; no horizontal scroll at 390 px). `/review/blr_flat` shows the blocked 2-month-cap claim in red (4.3 ready; steps in `frontend/README.md`). Submitting the form with the built year blank shows the `needs_input` question card. `lib/types.ts` is a first draft of the shapes `backend/models.py` should return; section ids used in the stub (`KRA-2(3)(e)`, `KRA-2(3)(f)`, `ICA-74`, `TPA-106`, `TPA-108`, `MTA-11`) need to match `law/karnataka.json` (3.4).

Checkpoint 1 shared items (Wasih): README Status, Before and after, Run the frontend and Credits updated for the frontend (4.1; Hasan to add backend ticks). 3.4 in progress: contract drafted in `docs/api-contract.md` for `backend/models.py` to follow.
