# Frontend/backend contract (draft)

What the frontend expects from `backend/main.py`. Field names and literals match `frontend/lib/types.ts`; `backend/models.py` should use the same ones (TASKS.md 3.4). A worked example of every shape is in `frontend/stubs/blr_flat.json`. Change this file, `types.ts` and `models.py` together.

## Endpoints (BUILD.md Phase 5)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/runs` | multipart: `file` (PDF) or `text`, `facts` (JSON string of `Facts`), `language` | `{ "id": str }` |
| GET | `/api/runs/{id}` | — | `Run` |
| POST | `/api/runs/{id}/answer` | `{ "field": str, "value": str }` | anything; the frontend re-fetches the run |
| POST | `/api/runs/{id}/approve` | `{ "draft_id": str }` | anything; the frontend re-fetches the run |
| GET | `/api/moveout/{id}` | — | `MoveoutRun` (Phase 7) |

The frontend polls `GET /api/runs/{id}` every 1.5 s while `status` is `running`. CORS must allow `http://localhost:3000`.

## Facts

| Field | Type |
|---|---|
| `rent_per_month` | int or null |
| `deposit_inr` | int or null |
| `built_year` | int or null (null is allowed: the agent must ask) |
| `substantial_renovation_year` | int or null |
| `local_body` | `"municipal_corporation"`, `"city_municipal_council"`, `"other"` or null |
| `premises_use` | `"residential"` or `"non_residential"` |
| `language` | `"en"` or `"kn"` |

## Run

| Field | Type | Notes |
|---|---|---|
| `id`, `task`, `title` | str | |
| `status` | `"running"`, `"needs_input"`, `"awaiting_approval"`, `"approved"`, `"failed"` | `needs_input` shows the question card |
| `created_at` | ISO datetime | |
| `model` | str | provider and model name |
| `facts` | `Facts` | |
| `governing_law` | `{ rent_act_applies: bool, summary: str, section_ids: [str], governs: [str] }` or null | null until `check_jurisdiction` has run |
| `trace` | `[TraceStep]` | in order; `index` starts at 0 |
| `findings` | `[Finding]` | |
| `drafts` | `[Draft]` | |
| `sections` | `{ section_id: Section }` | every id referenced anywhere in the run, so the UI can link it |
| `max_tool_calls` | int | 12 |
| `not_a_lawyer` | `true` | |
| `notice` | str | not-a-lawyer text |

## TraceStep

Each step has `index` (int), `at` (ISO datetime) and `type`. The `type` decides the remaining fields.

| `type` | Extra fields |
|---|---|
| `plan` | `steps: [str]` |
| `question` | `field` (a `Facts` key), `question: str`, `why: str`, `answer: str or null` |
| `tool_call` | `tool: str`, `input: object`, `output: any`, `summary: str` (one line for the UI) |
| `verifier` | `claim: str`, `section_id: str or null`, `verdict: "cited" or "unverified" or "blocked"`, `reason: str` |
| `draft` | `draft_id: str`, `tone: "request" or "challenge" or "notice"` |
| `approval` | `draft_id: str`, `approved: bool`, `follow_up_date: "YYYY-MM-DD" or null` |

## Finding, Draft, Section

- `Finding`: `clause_ref` (e.g. "Clause 6"), `clause_text`, `category` (`deposit_forfeiture`, `lock_in`, `painting_or_cleaning_fixed`, `notice_shortfall`, `rent_escalation_excess`), `issue`, `ask`, `section_ids: [str]`, `money_at_risk_inr: int`, `money_note: str or null`, `severity` (`high`, `medium`, `low`).
- `Draft`: `id`, `tone`, `to`, `text: { "en": str, "kn": str }`. The backend provides both languages; the UI toggles between them.
- `Section`: `id`, `act`, `section`, `title`, `source_url`, `applies_in_karnataka: bool`. This is the `law/karnataka.json` entry without its text.

## Section ids used by the stubs

`KRA-2(3)(e)`, `KRA-2(3)(f)`, `ICA-74`, `TPA-106`, `TPA-108`, `MTA-11` (the Model Tenancy Act deposit cap, `applies_in_karnataka: false`). If `law/karnataka.json` uses a different scheme, the stubs will be renamed to match.
