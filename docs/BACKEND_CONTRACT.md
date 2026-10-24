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
