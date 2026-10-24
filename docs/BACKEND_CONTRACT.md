# Backend handoff

Backend work lives on `hasan/backend`. Frontend ownership remains with W.
Frontend/API schemas will be published here as the API phase is implemented.

## Phase 1: law tools

`backend.tools.law.lookup_section(id)` returns the entry from
`law/karnataka.json`, or `None` for an unknown id. Canonical model-law ids are
`MTA-11(1)` (deposit cap) and `MTA-30` (Rent Authority); both are explicitly
inapplicable in Karnataka. An entry's `applies_in_karnataka` flag describes the
law pack, not coverage of an individual property.

`check_jurisdiction(rent_per_month, built_year, local_body, premises_use,
substantial_renovation_year=None, ...)` returns:

```json
{
  "applies": null,
  "reasons": [
    {"section_id": "KRA-2(3)(e)", "status": "needs_input", "text": "..."}
  ],
  "missing": ["standard_rent_monthly"],
  "note": "...",
  "questions": ["..."]
}
```

`applies` is `false` for a known exclusion, `null` when unresolved, and `true`
only conditionally on all supplied confirmations. Reasons have `excluded`,
`needs_input`, or `conditional` status. Render the missing field names and
reasons; do not present `null` as excluded. The prototype supplies additional
questions when its screening remains unresolved.

Supported confirmed First Schedule local bodies are `municipal_corporation`
and `city_municipal_council`. `premises_use` must be `residential`; PG/lodging,
commercial exceptions and other local bodies need separate review. Optional
keyword facts are `standard_rent_monthly`, `ownership_type`,
`other_exemptions_checked`, and `tenancy_date` (ISO date). A missing renovation
year means no substantial renovation has been reported. The calendar year
alone cannot resolve the exact fifteen-year anniversary; `completion_date`
in `missing` means obtain the exact date for manual review. `as_of` is a Python
date override for deterministic tests, not an API input.

## Corrections to the planned examples

The [official Karnataka Rent Act](https://www.indiacode.nic.in/bitstream/123456789/7810/1/34_of_2001_e.pdf)
section 2(3)(e) uses deemed/standard rent, not current monthly market rent.
The existing `housing.legal` screen already preserves this distinction. The
wrapper imports it and collects independent exclusions without changing it.

The planned old-building CMC example at INR 3,000 is excluded if that amount
is confirmed statutory rent: Part B's threshold is INR 2,000. Tests cover that
exclusion and conditional coverage at INR 2,000. A market rent of INR 3,000
with confirmed statutory rent of INR 2,000 can qualify conditionally.

The five-argument modern-flat example returns `false` based on construction
age and reports `KRA-2(3)(e)` as needing statutory-rent input. Both exclusions
are reported when statutory rent is explicitly confirmed above the threshold.
Unknown facts are never silently confirmed to make an example pass.

## Validation

Phase 1: 72 tests and 6 subtests pass using the prototype's Python 3.10.11
environment. Python 3.11 event-environment setup remains pending.

## Phases 2 and 3

`backend.agent.verifier.verify_claims([{text, section_id}])` returns Pydantic
`Verdict` objects with `text`, `section_id`, `verdict` and `reason`. Verdicts are
`cited`, `unverified`, or `blocked`. This checks citation identity and model-law
exclusion, not semantic entailment or property coverage. A real section id does
not by itself prove a claim correct. Keep this distinction in UI wording.

`python -m env.scorer env/tasks/blr_flat.json env/tasks/sample_run.json`
prints a perfect **3/3**. Substitute `sample_run_wronglaw.json` to demonstrate
the **−1** wrong-law penalty. These samples are synthetic outputs, not model
benchmark results. `env.scorer.score(task, run)` accepts findings with
`clause_ref`, `category`, integer `money_at_risk_inr`, and `section_ids`, plus
`governing_law` and optional `claims`. Missing, duplicate or misidentified
findings do not earn full money credit. INR 500 error is inclusive.

`read_agreement(text_or_pdf_bytes)` returns `clauses: [{id, text, page}]`,
`redactions: {aadhaar, pan, phone}`, and total `redaction_count`. It reuses the
prototype clause splitter and limits. No uploaded document is persisted. No
OCR is run; scanned, empty or locked PDFs require verified pasted text.

`compute_money(category, inputs)` returns integer INR, with fractional rupees
rounded half up. Inputs by category:

| Category | Inputs |
| --- | --- |
| `deposit_forfeiture` | `deposit`, boolean `on_any_breach` / `on_early_exit` |
| `lock_in` | `monthly_rent`, `remaining_months` |
| `painting_or_cleaning_fixed` | `amount` |
| `notice_shortfall` | `monthly_rent`, `required_months`, `given_months` |
| `rent_escalation_excess` | `monthly_rent`, `escalation_percent` |

The escalation threshold of ten percent is a product preference, not a legal
cap. These amounts describe exposure, not guaranteed compensation or recovery.

`draft_message(findings, tone, language)` returns `text`, `tone`, `language`,
and `translation_note`. Languages: `en`, `kn`. Tones: `request`, `challenge`,
`notice`. Structured numerical preferences reuse prototype templates;
unstructured findings receive generic clarification requests, not purported
translations of arbitrary source prose.

`send_and_schedule(message, approved)` rejects everything except literal
`True`. It returns `id`, `message`, `status: scheduled`, `follow_up_date`
(seven days later), and `delivery_status: not_sent`. There is no external
delivery integration or durable scheduler. Never label this result "sent".

Checkpoint validation: **132 tests and 6 subtests passed**. Phase 4's backend
terminal demonstrations have been run. W's frontend, browser demonstration
and shared checkpoint attendance are pending. Phase 5 has not started.
