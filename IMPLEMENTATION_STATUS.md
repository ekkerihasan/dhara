# City housing implementation status

Updated: 18 October 2026. Implemented with three parallel agents plus integration work. No model API integration or `.env` is required for the offline demo.

## Delivered

- Six-clause `residential_lease` OpenEnv scenario with three client-preference conflicts, two counteroffers, and a 22-step budget. Deposit and notice limits are preferences, not asserted legal limits.
- Clarification returns property/client facts instead of benchmark answers for the new scenario. Revisions have repetition detection and per-clause attempt limits.
- Standalone `housing` package: clause extraction with page/line references, jurisdiction status, explicit numeric preference checks, proposed wording, and an action trace.
- Complete English, Kannada and Hindi templates for structured requests; arbitrary original clauses are not automatically translated.
- Browser negotiation connected to review findings: counter, clarify, accept or escalate, with refreshed drafts and preserved accepted wording.
- Local browser interface for pasted text, text PDFs, photos and scanned PDFs. Extraction/OCR stays local; users confirm text before review. Documents stay in memory; request logging is disabled.
- Command-line review, synthetic example document, eight-case reproducible offline evaluation, and unit tests.
- Curated official Karnataka section 2 applicability sources and section 49(1) essential-services rule. The screen distinguishes missing facts, encoded exclusions and conditional applicability. Statutory rent is kept separate from current market rent. See `docs/LEGAL_SCOPE.md` for verification method and coverage limits.
- Copyable multilingual drafts, accepted clause wording, a loadable demo, and review/history JSON export.

## Run locally

From the repository directory:

```powershell
.\.venv\Scripts\python.exe housing_ui.py --port 7861
```

Open `http://127.0.0.1:7861` and click **Load demo agreement**, or upload `examples/negotiation_lease.txt`. A deposit offer of 4 months is countered; 2 months can be accepted. A 30-day termination notice resolves the other numeric conflict. Jurisdiction facts remain unresolved until confirmed; review preferences still work.

The interface itself has no third-party dependencies. If you have another working Python 3.10+ installation, `python housing_ui.py` also works. On this machine, the default `python` currently points to a broken unrelated virtual environment, so prefer the explicit project interpreter above.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe evaluate_housing.py --output evaluation/offline_results.json
.\.venv\Scripts\python.exe evaluate_negotiation.py --output evaluation/negotiation_results.json
.\.venv\Scripts\python.exe verify_housing.py --ocr --output evaluation/document_smoke_results.json
```

Environment tests require the dependencies from `pip install -e ".[dev]"`. PDF/image intake requires `pip install -r requirements-housing.txt`; those dependencies are installed in the current `.venv`. OCR uses bundled local models, with no API calls. Limits: 8 MB, 25 PDF pages, 64 reviewed clauses; arbitrary agreements and handwriting are not guaranteed to extract correctly.

## Validation

- Offline review tests include an integration-discovered correction separating termination notice from landlord entry notice.
- Offline evaluation: 8/8 synthetic development fixtures pass. See `evaluation/offline_results.json`; these results do not establish legal accuracy or model improvement.
- Python compilation and JavaScript syntax checks passed.
- Five HTTP tests pass, including document extraction → review → accepted offer, preference passthrough, malformed inputs, size limits, and cross-origin rejection.
- Full unittest suite: **51/51 passed**; covers documents, language templates, conditional legal screening, negotiations, lease scoring, private grading fields and existing scenario resets.
- Real local OCR and end-to-end synthetic smoke: 4/4 passed for text, text PDF, PNG and scanned PDF through extraction, review and accepted negotiation. See `evaluation/document_smoke_results.json`.
- Scripted duplicate-offer control: six repeated actions versus bounded stopping after two; neither reaches agreement. This tests loop stopping, not LLM improvement.
- Project dependencies installed successfully in `.venv`. No model API requests were made.

## Deferred or outside this offline delivery

1. Model-driven planning, external API integration and live old-baseline/new-agent benchmarking remain deferred as requested until credentials are available.
2. Legal review is deliberately narrow: encoded applicability screening and one conditional essential-services rule. Broader statutory analysis, independent factual verification, other jurisdictions and legal professional review are not completed by this prototype.
3. Kannada/Hindi use complete structured templates, not free-form translation; native-language review remains outstanding.
4. OCR is tested on synthetic English inputs, not a representative real-world document corpus. It requires user confirmation.
5. Shop leases, RERA homebuyer agreements and speech remain stretch goals.

The complete offline input → review → negotiation → message workflow is delivered for the scoped residential prototype. It is not a production-ready legal agent or an evaluated autonomous LLM system.
