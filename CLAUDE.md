# CLAUDE.md: Dhara AI (dhara-tenancy)

Read this file fully before any task. It is the source of truth for Claude Code during ChronoForge 2026 (24 to 25 Oct 2026, IST).

## What we are building

Dhara AI is an agentic tenancy copilot for Karnataka's cities. It works out which law governs a rental, flags and negotiates unfair clauses before signing, keeps dated move-in evidence, and contests unfair deposit deductions at move-out. The tenant approves every outgoing message. Languages: English and Kannada (must), Hindi (stretch).

Hackathon: ChronoForge 2026, NITK Surathkal, online. Track: Agentic AI. Theme: Cities of the Future. Judges score Problem Relevance, Innovation, Technical Implementation, Functionality, Impact and Practicality, Scalability, User Experience, Track Alignment, plus (for Agentic AI) meaningful autonomy, tool integration, planning, and measurable value beyond a conventional chatbot.

## Repo history rule (important)

- The first commit is a permitted import of the team's earlier offline prototype (April 2026, no model). The organisers confirmed this in writing. README has a "Note on prior work" section at the end. Never remove it.
- Everything in the README "Built at ChronoForge" checklist must be written during the event. Do not claim earlier work as new.
- Commit small, working pieces at least once an hour. No empty commits. No filler commits. Use the commit message given in the task.
- Each member commits under their own git identity. Check `git config user.name` before the first commit of a session.

## Hard rules (disqualification risks)

1. Never write a secret into any tracked file. Keys come only from environment variables: `GROQ_API_KEY`, `SARVAM_API_KEY`, `MODEL_PROVIDER`. `.env` and `.env.*` are ignored; `.env.example` holds placeholder names with empty values only.
2. Before every commit run: `git diff --cached | grep -iE "api[_-]?key\s*=\s*['\"]?[A-Za-z0-9]{12,}"` and stop if anything matches.
3. Credit third-party code, data and models in README Credits (India Code, PRS India, Sarvam, Groq, OpenEnv, any npm or pip package that is not standard).
4. Do not store uploaded documents on disk. Keep them in memory for the request. Redact Aadhaar (12 digits, optional spaces), PAN (5 letters 4 digits 1 letter) and Indian phone numbers (10 digits, optional +91) before any model call.
5. Every legal claim in model output must carry a section id that exists in `law/karnataka.json`, or be marked `unverified`. The verifier enforces this. Never bypass it for a demo.

## Stack

- Backend: Python 3.11, FastAPI, Pydantic v2, httpx, pytest. Lives in `backend/`. The earlier prototype code in `housing/` and `server/` is reused by import, not rewritten. Wrap it; do not duplicate it.
- Agent model: Sarvam-105B if tool calling passed the pre-event test, otherwise Groq `llama-3.3-70b-versatile`. One provider module `backend/llm/provider.py` with a single `chat(messages, tools) -> ToolCallOrText` function. Nothing else imports a provider SDK directly.
- Frontend: Next.js (App Router, TypeScript, Tailwind) in `frontend/`. Talks to the backend over JSON at `NEXT_PUBLIC_API_URL`. Has a `USE_STUBS` flag so screens work before the backend does.
- Law data: `law/karnataka.json`. Data, not code. Each entry has id, act, section, title, text or paraphrase, source_url, applies_in_karnataka, notes.
- Scoring: `env/tasks/*.json` (three tasks) and `env/scorer.py`. Deterministic. No LLM in the scorer.

## Folder layout

```
dhara-tenancy/
  CLAUDE.md  BUILD.md  TASKS.md  README.md  .env.example  .gitignore
  law/karnataka.json
  backend/
    main.py              FastAPI app, routes under /api
    llm/provider.py      single model entry point
    tools/law.py         check_jurisdiction, lookup_section
    tools/agreement.py   read_agreement (PDF text extraction, PII redaction)
    tools/money.py       compute_money
    tools/messages.py    draft_message (EN, KN; HI stretch), send_and_schedule (approval gate)
    agent/verifier.py    citation check
    agent/tenant.py      planning loop, tool dispatch, trace recording
    agent/moveout.py     Flow 2
    models.py            Pydantic schemas shared with frontend
  env/
    tasks/blr_flat.json  pg_room.json  moveout.json
    scorer.py            checks + wrong-law penalty
    run_eval.py          baseline vs agent runner, writes results/scores.md
    results/
  frontend/              Next.js app
  housing/  server/  static/  tests/   (prototype, reused by import)
  docs/                  screenshots, demo script
```

## Verified law facts (do not change without a source)

- Karnataka has NOT adopted the Model Tenancy Act 2021. Its 2-month deposit cap and Rent Authority do not apply in Karnataka. Citing them as binding is the "wrong-law" case and must be penalised.
- Karnataka Rent Act 1999 (Act 34 of 2001, amended by Act 07 of 2026):
  - s.2(1): Chapters I to III and V to VIII apply to First Schedule areas.
  - First Schedule Part A: areas within Cities under the Karnataka Municipal Corporations Act 1976 plus 3 km around them. Part B: City Municipal Councils under the Karnataka Municipalities Act 1964. Bengaluru, Mysuru, Mangaluru are Part A.
  - s.2(3)(e): Act does not apply where standard rent exceeds Rs 3,500/month in Part A areas, Rs 2,000/month elsewhere.
  - s.2(3)(f): does not apply for 15 years after construction or substantial renovation.
  - s.2(3)(g): most non-residential premises excluded.
  - Result: most modern city flats fall outside the Act. The agent must say so, not pretend the Act protects the tenant.
  - s.3: "Court" for the City of Bangalore means the Court of Small Causes.
  - s.4: written agreement required where the Act applies.
  - s.15: refund of sums paid in breach of the Act, claim within 1 year.
  - s.16: tenant entitled to rent receipt; penalty up to double the amount for refusing.
  - s.48(3): landlord entry only after notice.
  - s.49: no cutting essential supplies.
  - No deposit cap exists in the Act.
- Registration Act 1908 s.17: lease over 1 year must be registered (why 11-month agreements exist).
- Indian Contract Act 1872 s.74: only reasonable compensation recoverable; excessive forfeiture is a penalty.
- Transfer of Property Act 1882 s.106 (notice to quit) and s.108 (rights and liabilities of lessor and lessee) govern leases outside the Rent Act. Quote only what you can source.
- Recovery routes (Flow 2 "next formal step"): written demand, then legal notice, then Rent Controller where the Act applies, otherwise civil money-recovery suit (Small Causes Court in Bengaluru within its limit, limit unverified). Consumer forum via e-Daakhil is contested; mark it uncertain. Do not suggest a police complaint.
- Sources: India Code https://www.indiacode.nic.in/bitstream/123456789/7810/1/34_of_2001_e.pdf ; PRS https://prsindia.org/billtrack/the-model-tenancy-act-2021

## Money at risk (deterministic formulas, used by compute_money and the scorer)

- deposit_forfeiture: full deposit amount if the clause allows forfeiture on any breach or on early exit; else 0.
- lock_in: monthly_rent x remaining lock-in months.
- painting_or_cleaning_fixed: the fixed amount stated in the clause (or the landlord's claimed deduction in Flow 2).
- notice_shortfall: monthly_rent x (required notice months minus given notice months), minimum 0.
- rent_escalation_excess: (escalation percent minus 10) percent of annual rent if escalation above 10 percent per year; else 0. The 10 percent is a product threshold, not a legal limit; label it so.
- Every finding reports `money_at_risk_inr` as an integer. Scorer tolerance is Rs 500.

## Agent contract

- The tenant agent runs a loop: plan (list intended tool calls), ask (if a jurisdiction input is missing, stop and ask the tenant), act (call tools), verify (every claim through the verifier), draft (messages), wait for approval.
- Every step is appended to `trace: list[TraceStep]` with type in {plan, question, tool_call, verifier, draft, approval}. The frontend renders this trace. If it is not in the trace, it did not happen.
- Max 12 tool calls per run. Identical repeated calls are blocked.
- Outputs carry `not_a_lawyer: true` and the notice text.

## Coding standards

- Type hints everywhere in Python; Pydantic models for every API payload; the same shapes in `frontend/lib/types.ts`.
- Tests for every tool and for the scorer. `pytest -q` must pass before each commit.
- Small functions, no clever abstractions. This code will be explained live to judges.
- Log tool calls at INFO with inputs truncated to 200 chars; never log document text.

## Do not

- Do not add new frameworks, ORMs, databases or queues. In-memory dicts keyed by run id are enough for 24 hours.
- Do not rewrite `housing/` or `server/`. Import from them.
- Do not build photo OCR, voice, WhatsApp or Hindi until TASKS.md marks all must-have items done.
- Do not invent statistics or section text. If unknown, say unverified.
