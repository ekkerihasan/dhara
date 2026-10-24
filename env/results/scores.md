# Baseline vs agent (2026-10-25, openai/gpt-oss-120b)

Same model, same agreement, same law pack. The baseline has no tools and no verifier. One run each; scores are out of 4 on the two pre-signing tasks (two negotiation rounds against the strict owner) and out of 3 on moveout.

| Task | Mode | Governing law | Money within Rs 500 | Citations exist | Negotiation correct | Wrong-law penalty | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| blr_flat | baseline | 0 | 1.00 | 1.00 | 1.00 | 0 | **3.00** |
| blr_flat | agent | 1 | 0.80 | 0.92 | 1.00 | 0 | **3.72** |
| pg_room | baseline | 0 | 1.00 | 1.00 | 1.00 | 0 | **3.00** |
| pg_room | agent | 1 | 1.00 | 1.00 | 0.67 | 0 | **3.67** |
| moveout | baseline | 0 | 1.00 | 1.00 | n/a | 0 | **2.00** |
| moveout | agent | 1 | 1.00 | 0.75 | n/a | 0 | **2.75** |
