# Model-driven landlord negotiation (8.1)

This is negotiation practice with a **simulated** landlord. It never contacts a landlord, changes an agreement, or sends a message. Acceptance is a simulated willingness to amend terms, not a legal-validity finding.

Start the backend using the normal provider environment variables. The landlord uses the same `backend.llm.provider.chat` boundary as the tenant agent. No new provider SDK or credential is required.

For a browser demo, open `/negotiate` in the frontend. It offers the PG example, English/Kannada replies, an approval checkbox for each proposal, and the live conversation. The page always calls the backend rather than presenting scripted sample replies as model output.

Start with the PG example:

```http
POST /api/negotiations
Content-Type: application/json

{
  "task_id": "pg_room",
  "tenant_message": "Please replace blanket deposit forfeiture with documented reasonable loss, and provide evidence for cleaning deductions.",
  "approved": true,
  "language": "en"
}
```

Poll `GET /api/negotiations/{id}` until status changes from `running`. Each turn contains a model-produced `accept`, `counter`, or `reject` decision, a reply, and a verifier result for every statement. `ready` means another proposal can be submitted; `accepted` and `exhausted` end the simulation.

```http
POST /api/negotiations/{id}/message
Content-Type: application/json

{
  "tenant_message": "I agree to reasonable cleaning costs supported by an invoice; please add that wording.",
  "approved": true
}
```

Every tenant proposal requires explicit approval, including follow-ups. There are at most three successful model rounds; identical proposals are rejected. The model receives the redacted agreement and actual prior offers and replies, not the fixture's legacy `landlord_pushback` list. To use another agreement, replace `task_id` with `agreement_text` and optional `facts` in the initial request. `language` supports `en` and `kn`.

The simulation supplies only the verified Contract Act section 74 context. Unknown, wrong-law, detected uncited legal claims, and citations outside that context block the reply. Explicit law IDs such as `ICA‑74` require a structured citation, including when Unicode dashes are used. A valid structured reply with blocked claims receives the actual verifier results as tool feedback and one opportunity to correct them: at most two model calls per round. A second failed verification ends the attempt without publishing that reply. Other bargaining statements remain visibly `unverified`; keyword-based legal-claim detection and citation checking do not establish that the model's interpretation is legally correct. Provider failures produce `failed`, never a canned response disguised as a model result. A failed proposal can be retried with explicit approval. Documents and conversation state remain in memory.

Run deterministic tests with `python -m pytest tests/test_landlord.py -q`. These use a fake provider to check contextual responses, follow-up history, approval, redaction, citation blocking, provider failure, and the round limit; they do not establish live model quality.

## Live smoke status

The final synthetic PG smoke on 25 October 2026 (IST) completed two live rounds with Groq **`openai/gpt-oss-20b`**: a contextual counter-proposal followed by simulated acceptance. It proposed an itemised cleaning invoice and documented-loss deductions. The explicit Contract Act reference carried `ICA-74`, no statement was blocked, and other statements remained visibly `unverified`. The actual conversation and provider metadata are preserved in [`landlord_smoke_groq.json`](../env/results/landlord_smoke_groq.json) and the latest-result alias [`landlord_smoke.json`](../env/results/landlord_smoke.json). This run used two provider calls; the bounded correction path is covered by deterministic regression tests.

Earlier failed attempts remain separate:

- Groq `openai/gpt-oss-120b` returned HTTP 429 (rate limit); preserved in [`landlord_smoke_groq_gptoss120b.json`](../env/results/landlord_smoke_groq_gptoss120b.json).
- Sarvam `sarvam-105b` returned an empty model response; preserved in [`landlord_smoke_sarvam.json`](../env/results/landlord_smoke_sarvam.json).
- An earlier Groq `openai/gpt-oss-20b` follow-up mentioned section 74 with `section_id: null` and was correctly blocked; preserved in [`landlord_smoke_groq_gptoss20b_before_correction.json`](../env/results/landlord_smoke_groq_gptoss20b_before_correction.json).

Nothing was sent. Simulated acceptance does not validate legal meaning or change a real agreement. These are single synthetic runs, not a model-quality benchmark. The verifier checks citation identity and explicit reference attachment, not semantic entailment; unverified statements can still contain overconfident wording.

After provider capacity is available, reproduce with `python -m env.run_landlord_smoke --provider groq` or `--provider sarvam`. Omitting the option respects `MODEL_PROVIDER`. The runner reads local `.env` without printing credentials, writes synthetic results and credential-free provider diagnostics, and exits nonzero if the simulation fails.

To reproduce the smaller-model attempt, set `GROQ_MODEL=openai/gpt-oss-20b` only for the process running the smoke test. The application's default model remains unchanged.
