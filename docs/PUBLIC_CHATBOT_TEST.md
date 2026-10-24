# Public chatbot test — exact prompts

Status: **test harness implemented; no public-chatbot responses collected yet**. This is separate from the Groq baseline-versus-agent evaluation. [Codex reference answers](CODEX_REFERENCE_ANSWERS.md) are available, explicitly excluded from the public comparison.

## Run protocol

Use the same questions in ChatGPT and Gemini, preferably in a fresh conversation for each. Do not supply the answer key, Dhara's law pack or previous chatbot answers. Keep settings the same across questions and record whether browsing is enabled. One batch per product is acceptable only if recorded as a batch, not ten independent conversations.

For every response record: service, displayed model (or `not displayed`), date/time and time zone, question id, verbatim answer, browsing setting, and a share link or saved transcript. Do not infer model identity from what the chatbot says about itself. Use only these synthetic facts.

## Common instruction

This is a synthetic residential-tenancy question about Karnataka, India, asked on 24 October 2026. Answer in no more than 150 words. Identify the relevant Act and section for legal claims. Distinguish a binding rule from a model law, a contractual term, or a suggestion. If information is missing or you cannot verify current law, say so.

## Questions

### Q01 — Model-law deposit cap

My Bengaluru landlord wants a deposit equal to six months of rent. Is the Model Tenancy Act's two-month residential deposit cap binding on this Karnataka tenancy? Does the size of the deposit alone prove the agreement is unlawful?

### Q02 — Modern-building exclusion

I rent a Bengaluru residential flat completed in 2019 for INR 25,000 per month. Its statutory standard/deemed rent has not been established. Can the Karnataka Rent Act apply in October 2026? Explain which facts establish an exclusion and which do not.

### Q03 — City Municipal Council threshold

The premises are in a confirmed First Schedule Part B City Municipal Council area in Karnataka, completed in 1980, with confirmed statutory standard rent of INR 3,000 per month. Other exclusions have been checked. A friend says the INR 3,500 threshold means the Rent Act applies. Is that correct?

### Q04 — Missing jurisdiction facts

A Bengaluru residential tenancy has current monthly rent of INR 25,000. Construction/renovation dates, statutory standard/deemed rent and ownership details are unknown. Can you confidently say the Karnataka Rent Act applies or does not apply? What must be checked?

### Q05 — Rent-escalation threshold

My Karnataka rental agreement proposes a 12 percent annual increase. Is a 10 percent annual increase a universal statutory maximum? Please separate any legal restriction from a suggested negotiation target.

### Q06 — Automatic forfeiture

My agreement says the entire INR 150,000 deposit is forfeited for any breach or early exit. Does that clause automatically entitle the landlord to the full amount in every case? What principle in section 74 of the Indian Contract Act is relevant?

### Q07 — Pre-existing damage and wear

At move-out from a private Bengaluru flat completed in 2019, the landlord claims INR 15,000 for faded paint and scuffs already recorded in our dated move-in checklist. The agreement excludes reasonable wear and tear. How should that deduction be assessed, and what is the relevance and limitation of TPA section 108(m)?

### Q08 — Lease registration

For a Karnataka residential lease with an 18-month term, is notarising the agreement a substitute for registration? Identify the relevant Registration Act and Transfer of Property Act provisions.

### Q09 — Essential services

Assume the Karnataka Rent Act has been confirmed to cover my tenancy. Can the landlord disconnect water merely to pressure me to pay a disputed charge? What does section 49 say, including its qualification?

### Q10 — Deposit recovery route and deadline

My private Bengaluru flat was completed in 2019. After I moved out, the landlord refused my written deposit-refund request; there is no allegation of fraud or violence. What formal steps should I consider? Is a Model Tenancy Act Rent Authority available, and is there automatically a statutory 30-day refund deadline?

## Review and reporting

The answer key and source links are in [the question fixture](../env/tasks/public_chatbot_questions.json). A reviewer classifies each actual answer as `correct`, `partial`, `incorrect`, or `unverified`, with a short reason and supporting source. Flag a `wrong_law` error separately only when the answer affirmatively applies the wrong law; simply mentioning a model law is not an error. A missing answer stays `not_run` and never counts as a pass or a chatbot failure. Preserve qualified answers rather than forcing them into an oversimplified legal rule.

A citation's existence alone does not establish that it supports the answer. A small, single-run test of ten chosen questions is not a general accuracy estimate.

## Current comparison

The machine-readable capture file is [public_chatbot_answers.json](../env/results/public_chatbot_answers.json); the generated comparison is [public_chatbot_report.md](../env/results/public_chatbot_report.md).

```powershell
# Create a blank capture file only if one does not already exist:
python -m env.public_chatbot_test init
# Record genuine answers, provenance, and source-backed reviews in that JSON, then:
python -m env.public_chatbot_test report
```

An actual capture requires the displayed model (or `not displayed`), a timestamp with a time-zone offset, verbatim answer and evidence reference. A review additionally needs a reviewer, reason and HTTPS source links. A Codex answer must use `service: Codex` and `access_method: self_reference`; it cannot be graded as an independent public observation. The reporter only marks the comparison complete after all 20 public responses are captured and reviewed. The template is never overwritten by `init`.

| Question | ChatGPT | Gemini |
| --- | --- | --- |
| Q01: Model-law deposit cap | Not run | Not run |
| Q02: Modern-building exclusion | Not run | Not run |
| Q03: City Municipal Council threshold | Not run | Not run |
| Q04: Missing jurisdiction facts | Not run | Not run |
| Q05: Rent-escalation threshold | Not run | Not run |
| Q06: Automatic forfeiture | Not run | Not run |
| Q07: Pre-existing damage and wear | Not run | Not run |
| Q08: Lease registration | Not run | Not run |
| Q09: Essential services | Not run | Not run |
| Q10: Deposit recovery route and deadline | Not run | Not run |

No accuracy percentages or comparative claims can be reported until real answers are captured and reviewed. Task 8.3 remains incomplete while access is unavailable.
