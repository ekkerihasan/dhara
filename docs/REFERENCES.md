# References

Sources for every number and legal statement in the [README](../README.md). Each source was opened and checked on 24 Oct 2026. Where a figure comes from a company study or a news report rather than official data, the row says so.

## Problem statistics

| Ref | Figure | Source | Type |
| --- | --- | --- | --- |
| R1 | 60.1% of households in BBMP (Bengaluru city corporation) live in rented homes (Census 2011) | [Bengaluru Housing and Houselisting Data, Census 2011](https://data.opencity.in/dataset/bengaluru-census-2011) (OpenCity mirror of Registrar General data) | Official data, mirrored |
| R2 | 24,47,718 urban rented households in Karnataka (Census 2011) | [Knight Frank, Institutionalising the Rental Housing Market in India, 2019](https://content.knightfrank.com/research/1004/documents/en/india-topical-reports-institutionalising-the-rental-housing-market-in-india-2019-6718.pdf) | Research report citing the Census |
| R3 | ₹31,628 crore held as security deposits by Bengaluru landlords (study published Jul 2026) | [NoBroker study, reported by Telugu Times](https://www.telugutimes.net/en/bnews/%E2%82%B91-26-trillion-locked-in-as-security-deposits-with-property-owners-study-353896.html) and [Business Standard](https://www.business-standard.com/markets/news/rs-1-26-trillion-locked-in-as-security-deposit-with-property-owners-study-126071600400_1.html) | Company study; method not public |
| R4 | Bengaluru deposits of six to nine months' rent, ₹3 to 5 lakh for one flat | [Business Today, 15 Apr 2025](https://www.businesstoday.in/amp/personal-finance/real-estate/story/the-biggest-scam-in-bengaluru-investment-advisor-calls-out-citys-rental-deposit-trap-472022-2025-04-15) | News report |
| R5 | One Bengaluru tenant paid ₹70,000 and got ₹18,000 back | [Free Press Journal](https://www.freepressjournal.in/amp/viral/3-mahine-ka-rent-choos-gaya-bengaluru-tenant-alleges-52000-deposit-deduction-from-70000-paid-to-landlord-viral-post-sparks-outrage) | A single reported case |

## Law

| Ref | Statement | Source |
| --- | --- | --- |
| R6 | Only four states (Andhra Pradesh, Tamil Nadu, Uttar Pradesh, Assam) have revised their tenancy law along the lines of the Model Tenancy Act, 2021; Karnataka is not one of them (latest government reply) | [PIB, Rajya Sabha written reply, 25 Jul 2022](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1844644); repeated by [LawStreet, Dec 2025](https://lawstreet.co/executive/fact-check-centre-has-not-notified-any-new-rent-law-claims-of-a-new-rent-agreement-act-2025-baseless) |
| R7 | The Model Tenancy Act, 2021 proposes a two-month residential deposit cap | [PRS Legislative Research](https://prsindia.org/billtrack/the-model-tenancy-act-2021) |
| R8 | The Karnataka Rent (Amendment) Act, 2025 (Act 07 of 2026), in force from 8 Jan 2026, replaces imprisonment with civil penalties and does not change deposits or rent revision | [Khaitan & Co, ERGO note, 17 Apr 2026](https://www.khaitanco.com/sites/default/files/2026-04/17042026%20-%20ERGO%20-%20Karnataka%20Rent%20(Amendment)%20Act.pdf) |
| R9 | The Karnataka Rent Act, 1999 does not apply above ₹3,500 a month standard rent in Part A areas, or for 15 years after construction (s.2(3)(e), (f)) | [Karnataka Rent Act, 1999, India Code](https://www.indiacode.nic.in/bitstream/123456789/7810/1/34_of_2001_e.pdf) |
| R10 | A lease over one year must be registered (s.17), which is why agreements run for 11 months | [Registration Act, 1908, India Code](https://www.indiacode.nic.in/bitstream/123456789/13236/1/the_registration_act%2C_1908.pdf) |
| R11 | A stipulated penalty supports only reasonable compensation (s.74) | [Indian Contract Act, 1872, India Code](https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf) |
| R12 | A tenant's restoration duty excepts reasonable wear and tear (s.108(m)); default notice for leases without a contract term (s.106) | [Transfer of Property Act, 1882, India Code](https://www.indiacode.nic.in/bitstream/123456789/14648/1/tpa.pdf) |

Every section the agent can cite, with its source link and whether it applies in Karnataka, is in [`law/karnataka.json`](../law/karnataka.json).

## Evaluation

| Ref | Result | Source |
| --- | --- | --- |
| R13 | Plain model vs agent scores on `blr_flat`, `pg_room` and `moveout` | [`env/results/scores.md`](../env/results/scores.md), produced by [`env/run_eval.py`](../env/run_eval.py); one live run each with `openai/gpt-oss-120b` on Groq |

## Not used

Widely repeated figures we left out because we could not trace them or they are out of date: "Karnataka capped deposits at two months in 2026", "Karnataka has partially adopted the Model Tenancy Act", a statutory "30-day deposit refund rule", "the Model Tenancy Act caps deposits at three months" (an earlier draft), and percentages of tenants who lose their deposit.
