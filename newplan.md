# Dhara AI: 24-hour city housing agent plan

The scoped offline workflow is implemented, including local PDF/OCR intake, conditional Karnataka screening, browser negotiation and complete language templates. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for validation and limits. Model integration and live model benchmarking remain deferred; broader legal coverage and stretch contract types remain outside this delivery.

## Goal

Build a demonstrable residential lease review agent for people moving to a city. It reads an agreement, establishes jurisdiction and relevant facts, retrieves verified legal sources, reviews clauses against law and user preferences, proposes revisions, and drafts a landlord message for human review.

Target: one supported state and one complete workflow today. Karnataka is the proposed first state because Kannada output fits the intended demonstration. Verify applicable legislation and coverage before enabling legal conclusions; do not assume the Model Tenancy Act applies.

## Existing foundation

- Reuse the OpenEnv environment, contract models, deterministic grading, baseline agent, and negotiation machinery.
- Preserve NDA, SaaS, and JV scenarios as regression examples.
- Current checkout: `fix/hackathon-api-env-variables`. At planning time, its upstream is current, while `origin/master` contains four additional commits. Inspect those changes before integrating relevant configuration fixes.
- Treat the existing keyword-based score as a task metric, not proof of legal correctness.

## Must ship

### 1. A residential lease scenario and evaluation fixtures

- Add a state-specific residential lease scenario with client requirements, clean clauses, problematic clauses, negotiation responses, and bounded steps.
- Include anonymized or synthetic lease fixtures with expected issues and verified supporting provisions.
- Include missing-location, unsupported-jurisdiction, clean-clause, and repeated-negotiation cases.
- Keep expected findings and grading answers private to the evaluator. Clarification returns user facts, not the answer key.

### 2. Document intake and jurisdiction checks

- Accept pasted text and text-based PDFs. Preserve page and clause references.
- Ask for property state/city and other facts required by the supported law's applicability rules.
- Let users confirm uncertain extracted facts before relying on them.
- Return a clear unsupported or unresolved result when applicability cannot be established.
- Do not treat model legislation as enacted state law.

### 3. An agent with explicit tools

- Tools: extract document text, retrieve supported legal provisions, request missing facts, review clauses, propose revisions, and draft a message.
- Use a small, curated collection of official sources with URLs, section identifiers, supporting passages, retrieval dates, and applicability notes.
- Track reviewed clauses, unresolved facts, negotiation history, and remaining actions.
- Prevent identical repeated actions; stop or escalate after bounded unsuccessful attempts.
- Show concise action progress and tool results in the interface.

### 4. Useful review output

- For each finding show the original clause, category, explanation, proposed wording, and any supporting legal citation.
- Distinguish potential legal conflicts, user-requirement conflicts, and negotiable or ambiguous terms.
- Never invent a provision or present an unresolved applicability question as a definitive violation.
- Draft an English landlord message and a Kannada version. Keep original monetary amounts, dates, obligations, and legal references consistent.
- Provide copyable messages for user review.

### 5. A complete interface

- Upload or paste agreement text, enter location and preferences, and run the review.
- Display missing-fact requests, review findings, citations, suggested revisions, and the landlord message.
- Keep uploaded documents out of logs and repository fixtures; avoid persistence unless necessary.
- Clearly state supported jurisdiction and input formats.

### 6. Measured comparison

- Run the old baseline and new agent on the same held-out scenarios, model, grading rules, and action budget.
- Report environment score, completion rate, repeated-action rate, issue precision/recall, citation correctness/applicability, latency, and token cost where available.
- Define repeated-action rate as duplicate normalized actions divided by total actions; also inspect semantic loops manually.
- Use manually reviewed expected findings and citations for the small legal evaluation set.
- Evaluate extraction separately using fixed documents and expected text/clauses.
- Save sanitized raw results and reproducible run commands. Report sample counts and failures; do not promise a score increase.
- If time permits, compare baseline plus loop prevention separately to isolate its contribution.

## Stretch goals, in order

1. Clear photo and scanned-PDF intake using OCR or a vision provider.
2. Hindi message output.
3. Sarvam text-to-speech, subject to credentials and integration time.
4. Shop lease scenario with separately verified applicability rules.
5. RERA homebuyer agreement workflow with its own sources and review criteria.

Do not let stretch features delay the complete residential lease demonstration.

## Execution schedule

| Hours | Work | Exit criterion |
|---|---|---|
| 0–3 | Inspect repository and upstream fixes; confirm source coverage and scenario fixtures | Supported jurisdiction, verified sources, and expected findings documented |
| 3–8 | Implement intake, missing-fact handling, retrieval, and structured findings | One agreement completes a cited review |
| 8–13 | Add negotiation tracking, repetition guards, and message drafting | Bounded negotiation finishes and produces a usable draft |
| 13–17 | Connect interface and Kannada output | Upload-to-message workflow works end to end |
| 17–21 | Run regression checks and controlled comparisons | Results saved; citation and applicability errors investigated |
| 21–24 | Fix demo failures and prepare presentation | Repeatable demo, setup instructions, and fallback recording/results |

These are timeboxes, not guarantees. Reduce scope when a must-ship milestone slips.

## Configuration and dependencies

- Python 3.10+ and project dependencies installed with `uv sync`.
- Configure `API_BASE_URL`, `API_KEY`, `MODEL_NAME`, and `SPACE_URL` through a local `.env`; commit only an example with placeholders.
- Select extraction and translation providers based on available credentials. Sarvam is optional.
- Existing server starts with `uv run server`; existing baseline runs with `uv run inference.py`.
- Document any new commands as they are implemented; the planned features are not available yet.
- Live model, translation, OCR, and speech checks require working credentials, network access, and provider availability.

## Validation and definition of done

- Existing scenarios still reset and accept valid actions.
- A supported lease completes extraction, jurisdiction checks, cited review, and message drafting.
- Missing facts trigger clarification; unsupported cases do not receive unsupported legal conclusions.
- Legal citations resolve to the curated official source and support the associated finding.
- Clean clauses are not automatically flagged, and preferences are not mislabeled as legal mandates.
- Repeated actions terminate or move to a defined fallback within the action budget.
- English and Kannada drafts preserve the material terms, with fluent-speaker review if available; document translation limitations otherwise.
- Baseline/new-agent comparison uses the same inputs and settings, with actual results recorded.
- Setup documentation, sanitized examples, and a reliable demo path are included.

## Demo narrative

“A person moving to a city uploads a rental agreement. Dhara asks for missing location facts, checks supported law, explains risky clauses with evidence, proposes changes, and drafts a message in the person's preferred language. Its negotiation behavior is evaluated against the original baseline.”

Show one legal finding, one preference-based finding, one unresolved case, and one completed negotiation. Use measured results rather than an assumed improvement.

## Delivery expectation

The scoped one-state residential workflow is the implementation target for today. Full multi-state coverage, all three new contract types, scanned documents, two regional languages, and speech are outside the core commitment. Legal-source verification and live-provider validation are dependencies; report any incomplete checks explicitly.
