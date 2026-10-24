# Dhara AI: Agentic Copilot for Fair Renting

An agentic tenancy copilot for Karnataka: review rental terms, negotiate changes, preserve move-in evidence, and challenge unfair deposit deductions with tenant approval.

Built for ChronoForge 2026, NITK Surathkal. **Track:** Agentic AI. **Theme:** Cities of the Future.

## Status

Phase 0: the earlier prototype has been imported without its Git history, local environment, credentials, or caches.

Checkpoint 1 (24 Oct, 16:00):

- [x] Next.js frontend on stubbed data: intake form, review report (governing law, money at risk, counter-proposal with EN/KN and approve, citation check, decision trace), question card for `needs_input`, and a move-out preview. `npm run build` and `npm run lint` pass; the layout works at 390 px. See [frontend/README.md](frontend/README.md).
- [x] Frontend/backend data shapes defined in `frontend/lib/types.ts`, with sample runs in `frontend/stubs/` checked against the law pack by `tests/test_frontend_stubs.py`.
- [x] Law library (`law/karnataka.json`, 25 sourced sections) with `check_jurisdiction` and `lookup_section` (`backend/tools/law.py`).
- [x] Citation verifier, three synthetic tasks and deterministic scorer (`backend/agent/verifier.py`, `env/`). The sample perfect run scores **3/3**; citing the model deposit cap incurs **−1** (2/3). These are scorer checks on synthetic outputs, not live model results.
- [x] `read_agreement` with in-memory PDF extraction and PII redaction, `compute_money`, English/Kannada `draft_message`, and the `send_and_schedule` approval gate. Approved drafts are recorded in memory; external delivery is not configured.
- [ ] Planning agent and live API (next).

Validation: **135 passed** (`python -m pytest -q`); **51 passed** at import. A root package import guard was added so pytest can collect tests from this checkout; `housing/` and `server/` are unchanged. Validation currently uses the earlier project's Python 3.10.11 environment; the event backend targets Python 3.11.

## Simple, scalable, secure

- **Simple.** Rules do the work wherever rules are enough. The Rent Act test, money-at-risk formulas, citation check and scorer are plain Python over JSON, with no model involved; the model plans which tools to call and states claims for the verifier, while reading, pricing, citation checks, drafts and scoring stay deterministic. Runs live in memory, with no database or queue.
- **Scalable.** Law is data. Each state is one JSON law pack (`law/karnataka.json` today) with a source link per section; the agent, verifier and screens stay the same for a new state.
- **Secure.** Keys come only from environment variables (`.env` is ignored). Uploaded agreements are kept in memory for the request, and `read_agreement` redacts Aadhaar, PAN and phone numbers before any model call. Claims citing a section that is missing from the pack or does not apply in Karnataka are blocked. Team planning notes are kept out of the repository.

## Before and after

| Existed before ChronoForge | Built at ChronoForge |
| --- | --- |
| Offline rules-based Karnataka applicability screening and clause extraction | Next.js review report with decision trace, verifier verdicts and money at risk (stubbed data) |
| English, Kannada and Hindi message templates | Approve-to-send draft panel with an English/Kannada toggle (stubbed data) |
| Scripted counterparty negotiation | Question card that pauses the run for a missing jurisdiction fact |
| Local PDF extraction and OCR | |
| OpenEnv tasks, deterministic grading and tests | |
| Offline housing review without a model; a separate legacy model inference script | |

## Built at ChronoForge

- [x] Sourced law library and jurisdiction tools
- [x] Citation verifier and wrong-law blocking
- [x] Three tenancy evaluation tasks and deterministic scorer
- [x] Agreement redaction, money calculations and approval-gated messages
- [ ] Model provider, planning agent and decision trace
- [ ] FastAPI run, answer and approval endpoints
- [ ] Next.js review and move-out screens with English and Kannada drafts (screens built on stubs; live API pending)
- [ ] Baseline versus agent evaluation results
- [ ] Move-out deduction challenges and next formal step


## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Stubs are on by default (`NEXT_PUBLIC_USE_STUBS`), so `/review/blr_flat` and `/moveout/moveout` work without the backend.

## Run the imported prototype

```powershell
python -m pip install -e '.[dev]'
python -m pip install -r requirements-housing.txt
python -m pytest -q
python housing_ui.py --port 7861
```

Open http://127.0.0.1:7861. The offline housing interface needs no model key. `.env.example` lists the planned event configuration; credentials belong only in an ignored local `.env` or environment variables.

## Credits

- Earlier Dhara AI prototype: imported from the team's Dhara-Ai repository; its existing source notices are preserved.
- Meta OpenEnv / openenv-core: environment interfaces and runtime, including FastAPI, Uvicorn, Pydantic, Gradio and websockets.
- Python dependencies: OpenAI Python SDK, python-dotenv, pytest, pytest-cov, httpx, setuptools and wheel.
- Local document tools: PyMuPDF, Pillow, RapidOCR, ONNX Runtime and NumPy. Event PDF extraction: [pypdf](https://pypdf.readthedocs.io/).
- [India Code](https://www.indiacode.nic.in/) and [PRS Legislative Research](https://prsindia.org/billtrack/the-model-tenancy-act-2021): planned statute and legislative references.
- Frontend: [Next.js](https://nextjs.org/), React and [Tailwind CSS](https://tailwindcss.com/) (MIT); [Lucide](https://lucide.dev/) icons (ISC); Geist and Geist Mono (Vercel, OFL-1.1) and Noto Sans Kannada (Google, OFL-1.1) via `next/font`.
- [Groq](https://groq.com/) and [Sarvam](https://www.sarvam.ai/): planned model providers; event integration and provider selection remain pending.

The imported README refers to a BSD-style LICENSE file, but the source checkout does not include that file. Upstream licensing information needs verification before distribution.

## Original prototype notes

The following documentation is preserved from the earlier project. Its model scores, validation statements and feature descriptions are historical prototype notes, not ChronoForge results.

---
title: Dhara AI Environment Server
emoji: 📜
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
base_path: /web
tags:
  - openenv
---

# Dhara AI

## City housing prototype — offline, no API key

A new local residential lease review prototype works without `.env` or model access:

```powershell
python housing_ui.py --port 7861
```

Open `http://127.0.0.1:7861` and select **Load demo agreement**, paste text, or upload a document. Text PDFs, photos and scanned PDFs use optional local extraction/OCR tools. Check extracted text before review.

The workflow extracts clauses, screens Karnataka applicability, identifies numeric preference conflicts and ambiguous wording, and drafts English/Kannada/Hindi requests using complete language templates. Findings support bounded counteroffers and preserve accepted wording. A narrowly scoped essential-services rule provides conditional section-level citations; this is not comprehensive legal review. See [legal scope](docs/LEGAL_SCOPE.md).

Run the command-line version or development-fixture evaluation:

```powershell
python -m housing examples/residential_lease.txt --state Karnataka --preferences '{"max_deposit_months":2,"max_notice_days":30}'
python evaluate_housing.py --output evaluation/offline_results.json
python evaluate_negotiation.py --output evaluation/negotiation_results.json
python verify_housing.py --ocr --output evaluation/document_smoke_results.json
python -m unittest discover -s tests -v
```

The text-only interface uses the Python standard library. For PDF and local OCR support install `python -m pip install -r requirements-housing.txt`. These tools run locally without API credentials. Environment tests additionally require the project dependencies. Limits: 8 MB per document, 25 PDF pages, and 64 reviewed clauses. The CLI also accepts `--facts` as a JSON object for the applicability checks.

The evaluations use synthetic development fixtures and a scripted repetition control. They are not live LLM comparisons or evidence of real-world legal/OCR accuracy. Model integration and model benchmarking remain deferred until API configuration is available.

The OpenEnv server also supports `task_name="residential_lease"`: a six-clause synthetic Bengaluru scenario with client-preference grading, two counteroffers, private grading fields, and bounded revisions. Existing NDA, SaaS, and JV tasks remain available.

Planning notes from the prototype are kept out of the repository.

**Dhara** (Sanskrit: *clause* or *section of law*) is an OpenEnv-compliant reinforcement learning environment for training AI agents to review, flag, and negotiate legal contract clauses.

Legal contract review is a task where AI agents must combine domain knowledge, multi-step reasoning, and strategic negotiation. Despite its real-world importance, RL environments for legal reasoning are scarce. Dhara AI fills this gap with three progressively harder contract scenarios, deterministic grading, and a multi-turn counterparty negotiation system that forces agents to balance client requirements against counterparty pressure.

Built for the **Meta PyTorch OpenEnv Hackathon x Scaler School of Technology (India, April 2026)**.

---

## How It Works

An agent receives a contract (a set of clauses) and a client brief with specific requirements. The agent must:

1. **Read** each clause and compare it against the client's requirements.
2. **Flag** clauses that violate those requirements and describe the issue.
3. **Revise** flagged clauses with new text that satisfies the client.
4. **Negotiate** with a simulated counterparty that pushes back on revisions (medium/hard tasks).
5. **Accept** clauses that are already compliant.
6. **Submit** the final review when all clauses are addressed.

Every action produces an immediate reward signal. Good flags, high-quality revisions, and correct negotiation decisions earn positive reward. False flags, weak revisions, and capitulating on hard client requirements are penalized.

---

## Tasks

| Task   | Contract Type              | Clauses | Issues | Negotiation                    | Max Steps | Difficulty |
|--------|----------------------------|---------|--------|--------------------------------|-----------|------------|
| `nda`  | Non-Disclosure Agreement   | 5       | 3      | None                           | 15        | Easy       |
| `saas` | SaaS Service Agreement     | 7       | 4      | 3 rounds, light pushback       | 25        | Medium     |
| `jv`   | Joint Venture Agreement    | 10      | 6      | 6 rounds, aggressive pushback  | 35        | Hard       |

**NDA (Easy):** A standard NDA between an Indian SaaS startup and a vendor. Three clauses contain issues (overly narrow confidentiality definition, perpetual duration, wrong jurisdiction). No counterparty negotiation. Tests basic issue identification and revision quality.

**SaaS (Medium):** A SaaS agreement between a healthtech company and a cloud provider. Four clauses need revision (data protection, deletion timelines, SLA terms, data residency). The counterparty pushes back on three revisions with alternative proposals that may or may not meet the client's requirements. The agent must decide when to hold firm and when a counter-offer is acceptable.

**JV (Hard):** A joint venture agreement between a 49%-stake Indian IT firm and a US tech partner. Six clauses need revision across IP ownership, deadlock resolution, non-compete scope, board composition, and exit valuation. The counterparty is aggressive, and clauses interact with each other (deadlock resolution affects board seats; exit terms affect valuation method). Agents that reason across clauses earn a cross-clause bonus.

---

## Action Space

The agent submits exactly one action per step as a JSON object:

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `flag_issue` | `clause_id`, `issue` | Mark a clause as problematic and describe why. |
| `suggest_revision` | `clause_id`, `revised_text` | Propose replacement text for a flagged clause. |
| `accept_clause` | `clause_id` | Accept a clause as-is (clean clauses) or accept a counterparty offer (during negotiation). |
| `request_clarification` | `clause_id`, `question` | Ask for more information about a clause. Returns the known issue or confirms the clause is standard. |
| `submit_review` | *(none)* | Finalize the review. Triggers completeness bonus if all clauses are addressed. |

Example action:

```json
{"action_type": "flag_issue", "clause_id": "clause_2", "issue": "Duration is perpetual; client requires max 3 years."}
```

### Clause State Machine

```
unreviewed --> flagged         (flag_issue)
unreviewed --> accepted        (accept_clause)
flagged    --> revised         (suggest_revision)
revised    --> revised         (suggest_revision, for iterative improvement)
revised    --> negotiating     (counterparty pushback, medium/hard tasks)
negotiating --> revised        (suggest_revision to reject counter-offer)
negotiating --> accepted       (accept_clause to accept counter-offer)
```

---

## Observation Space

Each observation contains:

| Field | Type | Description |
|-------|------|-------------|
| `contract_type` | `str` | e.g., "Non-Disclosure Agreement" |
| `client_role` | `str` | e.g., "Disclosing Party" |
| `client_requirements` | `List[str]` | Specific requirements the client needs met. |
| `clauses` | `List[ClauseInfo]` | Each clause: `id`, `title`, `text`, `status`, `negotiation_history`. |
| `steps_remaining` | `int` | Steps left before auto-termination. |
| `review_progress` | `str` | e.g., "3/5 clauses addressed". |
| `last_action_result` | `str` | Feedback on the previous action. |
| `last_action_error` | `str` | Error message if the previous action was invalid. |

---

## Reward Design

Rewards are **per-step**, not sparse end-of-episode. Each action type produces an immediate signal:

- **Correct flag** on a problematic clause: positive reward.
- **False flag** on a clean clause: negative penalty (applied in both issue identification and clean-clause handling components).
- **Revision quality**: scored by keyword matching against grading criteria. Higher quality text earns more reward. Delta-based: only the *improvement* over the best prior revision is rewarded, preventing farming.
- **Negotiation decision**: accepting a counter-offer that still meets client requirements is rewarded. Capitulating on a hard requirement is penalized.
- **Accepting a clean clause**: small positive reward.
- **Completeness bonus**: awarded if all clauses are addressed before submitting.
- **Cross-clause bonus** (JV only): awarded for detecting interactions between related clauses (deadlock/board, deadlock/exit).

All grading is **deterministic** (keyword/phrase matching). Same input always produces the same score. No LLM-as-judge, no randomness.

Final score = sum of all reward components, clamped to [0.0, 1.0].

---

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker (for containerized deployment)

### Install Dependencies

```bash
cd dhara_ai
uv sync
```

Or with pip:

```bash
pip install -e .
```

### Run the Server Locally

```bash
uv run server          # starts on port 7860
# or
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t dhara_ai .
docker run -p 7860:7860 dhara_ai
```

Verify:

```bash
curl http://localhost:7860/health
# {"status": "healthy"}
```

### Run Inference

The baseline agent in `inference.py` runs all three tasks sequentially against a running environment server:

```bash
# Set environment variables
export HF_TOKEN=<your-api-key>
export API_BASE_URL=https://api.groq.com/openai/v1   # or any OpenAI-compatible endpoint
export MODEL_NAME=llama-3.3-70b-versatile
export SPACE_URL=http://127.0.0.1:7860

# Run
uv run inference.py
```

The script accepts any OpenAI-compatible API (Groq, HuggingFace, OpenAI, Google Gemini, Together AI, etc.). Set `API_BASE_URL` and `MODEL_NAME` accordingly.

Output follows the required `[START]/[STEP]/[END]` format:

```
[START] task=nda env=dhara_ai model=llama-3.3-70b-versatile
[STEP]  step=1 action=flag_issue(clause_1) reward=0.12 done=false error=null
[STEP]  step=2 action=suggest_revision(clause_1) reward=0.10 done=false error=null
...
[END]   success=true steps=15 score=0.95 rewards=0.12,0.10,...
```

---

## Baseline Scores

Scores from a real end-to-end run using **Llama 3.3 70B** (via Groq) as the baseline agent:

| Task | Steps Used | Max Steps | Score | Notes |
|------|-----------|-----------|-------|-------|
| NDA | 15 | 15 | **0.95** | Correctly flagged all 3 issues, strong revisions, accepted clean clauses. |
| SaaS | 25 | 25 | **0.54** | Found all 4 issues but struggled with negotiation and false-flagged one clean clause. |
| JV | 35 | 35 | **0.47** | Found 5 of 6 issues, good initial revisions, but got stuck in action loops during negotiation. |

The score gap between easy and hard tasks demonstrates that the environment **meaningfully differentiates agent capability**. A perfect agent scores 1.00 on all tasks; the baseline LLM leaves significant room for improvement, particularly in multi-turn negotiation and cross-clause reasoning.

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check. |
| `/reset` | POST | Start a new episode. Body: `{"task_name": "nda"}` |
| `/step` | POST | Execute an action. Body: `{"action": {...}}` |
| `/state` | GET | Get current environment state. |
| `/schema` | GET | Get action/observation JSON schemas. |
| `/ws` | WebSocket | Persistent session for low-latency multi-step interaction. |
| `/web` | GET | Gradio web interface for interactive exploration. |

---

## Project Structure

```
dhara_ai/
├── Dockerfile              # Multi-stage Docker build (must be in root)
├── openenv.yaml            # OpenEnv metadata and task definitions
├── pyproject.toml           # Dependencies and project config
├── uv.lock                  # Locked dependency resolution
├── inference.py             # Baseline LLM agent
├── client.py                # EnvClient subclass with WebSocket session
├── models.py                # Pydantic models (Action, Observation, State)
├── README.md                # This file
└── server/
    ├── app.py               # FastAPI application
    ├── env.py               # Core environment: reset(), step(), state()
    ├── scenarios.py          # Contract data for all 3 tasks
    └── grader.py             # Deterministic grading functions
```

---

## Design Decisions

**Why keyword grading instead of LLM-as-judge?** Determinism. Same revision always gets the same score. No API calls from the environment, no randomness, no model availability dependency. The environment runs entirely self-contained on 2 vCPU / 8 GB RAM.

**Why delta-based revision rewards?** Prevents reward farming. An agent cannot repeatedly submit the same revision to accumulate reward. Only the marginal improvement over the best prior attempt is rewarded.

**Why multi-turn negotiation?** Single-turn flag-and-fix is too simple. Real contract review involves pushback. The counterparty simulation forces agents to reason about which client requirements are hard limits versus negotiable, adding a strategic dimension absent from most text-based RL environments.

**Why cross-clause bonuses?** In real joint ventures, clauses interact. Deadlock resolution terms affect board composition; exit clauses affect valuation methodology. Rewarding agents that detect these interactions tests a deeper level of legal reasoning.

---

## Validation

```bash
openenv validate    # passes all checks
```

---

## License

BSD-style license. See LICENSE file.

## Note on prior work

The first commit imports the team's earlier Dhara AI prototype as prior work, with organiser permission as recorded in the event instructions. The project plan identifies this as the April 2026 prototype; the local source snapshot also includes later offline housing work. The permission screenshot is kept outside this repository and has not been verified here.

The imported housing workflow runs offline without a model. The source also includes a separate legacy model inference script and historical model results, preserved under Original prototype notes; these are prior work. Every completed item in the Built at ChronoForge checklist must be written during the event. No imported feature or historical result is claimed as new event work.
