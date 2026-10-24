# Plain-model comparison endpoint

`POST /api/runs?mode=baseline` accepts the same text/PDF, facts, and language payload as a normal review. Poll `GET /api/runs/{id}` for the result. The default `mode=agent` retains the full review flow.

Baseline mode makes one provider call with no tools, using the redacted agreement and the law-pack context. It does not invoke the agent, fill omitted findings from rules, or pause to gather missing facts. Legal claims pass through the citation verifier after generation. Rent Act substantive claims remain blocked because this mode does not independently establish applicability.

The response explicitly identifies `mode: baseline`. Raw model findings and claims appear only in `baseline_output`, marked `verified: false` and `actionable: false`. The ordinary actionable `findings` and `drafts` arrays remain empty, and approval is refused. Inspect `verdicts` to see which model claims were blocked. Raw amounts are model estimates and can be wrong. This comparison is separate from the committed evaluation results; invoking it does not overwrite those artifacts.

Malformed model output and provider failures return status `failed`. They never silently substitute a rule-based agent review.
