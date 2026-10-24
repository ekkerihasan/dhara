# Baseline vs agent (2026-10-24, openai/gpt-oss-120b)

Same model, same agreement, same law pack. The baseline has no tools and no verifier. One run each; scores are out of 3.

| Task | Mode | Governing law | Money within Rs 500 | Citations exist | Wrong-law penalty | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| blr_flat | baseline | 0 | 1.00 | 0.80 | 0 | **1.80** |
| blr_flat | agent | 1 | 0.60 | 0.92 | 0 | **2.52** |
| pg_room | baseline | 0 | 1.00 | 1.00 | 0 | **2.00** |
| pg_room | agent | 1 | 1.00 | 1.00 | 0 | **3.00** |
| moveout | baseline | 0 | 1.00 | 1.00 | 0 | **2.00** |
| moveout | agent | 1 | 1.00 | 1.00 | 0 | **3.00** |
