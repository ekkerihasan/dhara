"""Build frontend/stubs/*.json from env/tasks/*.json by running the real backend tools.

Until the agent loop and API exist, the frontend shows these files. Every clause, rupee amount,
jurisdiction result, verifier verdict and draft below comes from the backend code; only the
wording the model would supply (the plan, each issue and ask, and the claims it wants to make)
is written here.

    python -m env.make_frontend_stubs
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.agent import scripted_landlord as landlord
from backend.agent.negotiation import letter_items
from backend.agent.verifier import verify_claims
from backend.models import Decision, Negotiation, NegotiationRound, TenantLimits
from backend.tools.agreement import read_agreement
from backend.tools.law import check_jurisdiction, lookup_section
from backend.tools.messages import draft_message, itemisation_letter
from backend.tools.money import compute_money
from env.scorer import score

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "env" / "tasks"
STUBS = ROOT / "frontend" / "stubs"
IST = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 10, 24, 11, 42, 5, tzinfo=IST)
AS_OF = date(2026, 10, 24)
NOTICE = (
    "Dhara AI is not a lawyer and this is not legal advice. It explains the agreement against the cited "
    "sections so you can negotiate; for a dispute, consult an advocate."
)

# What the model contributes for blr_flat: per finding, the money inputs it read from the clause,
# its wording of the issue and the ask, and a severity. Amounts are computed, never written here.
BLR_FINDINGS = {
    "C2": {
        "inputs": {"deposit": 150000, "on_any_breach": True, "on_early_exit": True},
        "issue": "The whole deposit is forfeited on any breach or early exit, whatever the landlord's actual loss. Excessive forfeiture is a penalty; only reasonable compensation is recoverable.",
        "ask": "Replace forfeiture with deduction of actual, itemised loss.",
        "severity": "high",
    },
    "C3": {
        "inputs": {"monthly_rent": 25000, "remaining_months": 6},
        "issue": "Leaving early costs the rent for all six remaining lock-in months, on top of the deposit forfeiture in C2.",
        "ask": "Cap the early-exit payment at one month's rent, or waive it if a replacement tenant is found.",
        "severity": "medium",
        "note": "Rs 25,000 x 6 remaining lock-in months.",
    },
    "C4": {
        "inputs": {"amount": 15000},
        "issue": "A fixed painting charge applies even if the walls are in the condition received. Restoration excludes reasonable wear and tear.",
        "ask": "Charge painting only for damage beyond reasonable wear and tear, judged against the dated move-in checklist.",
        "severity": "medium",
    },
    "C5": {
        "inputs": {"monthly_rent": 25000, "escalation_percent": 15},
        "issue": "A 15% yearly increase is above Dhara's 10% fairness threshold.",
        "ask": "Revise the increase to 10% a year.",
        "severity": "low",
        "note": "(15 - 10)% of Rs 3,00,000 annual rent. The 10% is a product threshold, not a legal limit.",
    },
    "C6": {
        "inputs": {"monthly_rent": 25000, "required_months": 2, "given_months": 1},
        "issue": "Two months' notice is required and one has been given, so one month's rent is exposed.",
        "ask": "Agree that the notice already given counts, or reduce the notice period to one month.",
        "severity": "medium",
        "note": "Rs 25,000 x (2 required - 1 given) months.",
    },
}

# Claims the model proposes. The verifier decides; two of these are meant to be blocked.
BLR_CLAIMS = [
    {"text": "The Karnataka Rent Act does not apply because the building was constructed in 2019, within the 15-year exemption.", "section_id": "KRA-2(3)(f)"},
    {"text": "The Rs 3,500 Part A ceiling depends on the statutory standard rent, which has not been confirmed, so it is not relied on.", "section_id": "KRA-2(3)(e)"},
    {"text": "Forfeiting the whole deposit on any breach or early exit is a penalty; only reasonable compensation for actual loss is recoverable.", "section_id": "ICA-74"},
    {"text": "A fixed painting charge ignores the exception for reasonable wear and tear.", "section_id": "TPA-108(m)"},
    {"text": "Notice is set by the agreement here; the Transfer of Property Act supplies the default only where the agreement is silent.", "section_id": "TPA-106"},
    {"text": "Karnataka law caps the security deposit at two months' rent.", "section_id": "MTA-11(1)"},
    {"text": "The landlord must refund the deposit within 30 days of the tenant vacating.", "section_id": None},
    {"text": "A 15% yearly increase is above Dhara's 10% fairness threshold.", "section_id": None},
]

PLAN = [
    "Read the agreement and split it into clauses (read_agreement, PII redacted first).",
    "Decide which law governs: run the Karnataka Rent Act applicability test (check_jurisdiction).",
    "Look up the sections I intend to rely on (lookup_section).",
    "Price each unfair clause in rupees (compute_money).",
    "Send every legal claim through the verifier before it reaches the tenant.",
    "Draft a counter-proposal for the landlord and wait for the tenant's approval.",
]


def section_meta(ids: set[str]) -> dict[str, dict[str, Any]]:
    out = {}
    for section_id in sorted(ids):
        entry = lookup_section(section_id)
        if entry is None:
            raise KeyError(f"{section_id} is not in law/karnataka.json")
        out[section_id] = {k: entry[k] for k in ("id", "act", "section", "title", "source_url", "applies_in_karnataka")}
    return out


class Trace:
    """Appends steps with increasing timestamps, the way the agent loop will."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.clock = START

    def add(self, step_type: str, seconds: int = 1, **fields: Any) -> None:
        self.clock += timedelta(seconds=seconds)
        self.steps.append({"index": len(self.steps), "type": step_type, "at": self.clock.isoformat(), **fields})

    def tool(self, name: str, tool_input: dict[str, Any], output: Any, summary: str) -> None:
        self.add("tool_call", tool=name, input=tool_input, output=output, summary=summary)


def build_blr_flat() -> dict[str, Any]:
    task = json.loads((TASKS / "blr_flat.json").read_text(encoding="utf-8"))
    facts = task["facts"]
    expected = {f["clause_ref"]: f for f in task["expected"]["findings"]}
    trace = Trace()
    trace.add("plan", seconds=0, steps=PLAN)

    agreement = read_agreement(task["agreement_text"])
    clauses = {c["id"]: c["text"].removeprefix(f"{c['id']}. ") for c in agreement["clauses"]}
    trace.tool("read_agreement", {"source": "text", "characters": len(task["agreement_text"])},
               {"clauses": len(agreement["clauses"]), "redactions": agreement["redactions"]},
               f"{len(agreement['clauses'])} clauses; {agreement['redaction_count']} personal identifiers redacted before any model call.")

    trace.add("question", seconds=2, field="built_year",
              question="In which year was the building constructed (or last substantially renovated)?",
              why="Section 2(3)(f) of the Karnataka Rent Act exempts a building for 15 years after construction. I cannot decide which law governs without it.",
              answer=str(facts["built_year"]))

    jurisdiction = check_jurisdiction(facts["rent_per_month"], facts["built_year"], facts["local_body"],
                                      facts["premises_use"], facts["substantial_renovation_year"], as_of=AS_OF)
    trace.tool("check_jurisdiction", {k: facts[k] for k in ("rent_per_month", "built_year", "local_body", "premises_use", "substantial_renovation_year")},
               jurisdiction, "Rent Act does not apply: s.2(3)(f) 15-year exemption. s.2(3)(e) needs the statutory rent, so it is left unresolved.")

    for section_id in ("ICA-74", "MTA-11(1)"):
        entry = lookup_section(section_id)
        applies = entry["applies_in_karnataka"]
        trace.tool("lookup_section", {"id": section_id},
                   {"id": section_id, "act": entry["act"], "section": entry["section"], "applies_in_karnataka": applies},
                   f"{section_id} found; " + ("applies in Karnataka." if applies else "applies_in_karnataka is false: Karnataka has not adopted the Model Tenancy Act."))

    findings = []
    for ref, model in BLR_FINDINGS.items():
        category = expected[ref]["category"]
        amount = compute_money(category, model["inputs"])
        trace.tool("compute_money", {"finding_type": category, "inputs": model["inputs"]}, amount, f"{ref} {category.replace('_', ' ')}: Rs {amount:,}.")
        findings.append({
            "clause_ref": ref, "clause_text": clauses[ref], "category": category,
            "issue": model["issue"], "ask": model["ask"], "section_ids": expected[ref]["expected_sections"],
            "money_at_risk_inr": amount, "money_note": model.get("note"), "severity": model["severity"],
        })

    for verdict in verify_claims(BLR_CLAIMS):
        trace.add("verifier", claim=verdict.text, section_id=verdict.section_id, verdict=verdict.verdict, reason=verdict.reason)

    drafts = {lang: draft_message(findings, "request", lang) for lang in ("en", "kn", "hi")}
    trace.tool("draft_message", {"findings": len(findings), "tone": "request", "language": ["en", "kn", "hi"]},
               {"draft_id": "d1", "characters": {lang: len(d["text"]) for lang, d in drafts.items()}},
               "Counter-proposal drafted in English, Kannada and Hindi (tone: request) from the findings.")
    trace.add("draft", draft_id="d1", tone="request")

    governing_law = {
        "rent_act_applies": jurisdiction["applies"],
        "summary": "The Karnataka Rent Act, 1999 does not apply to this flat: it was built in 2019, inside the 15-year exemption in s.2(3)(f). The Part A rent ceiling in s.2(3)(e) turns on the statutory standard rent, not the Rs 25,000 market rent, so it is not relied on. The lease is governed by the agreement itself, read with the Transfer of Property Act, 1882 and the Indian Contract Act, 1872.",
        "section_ids": ["KRA-2(3)(f)"],
        "reasons": jurisdiction["reasons"],
        "missing": jurisdiction["missing"],
        "note": jurisdiction["note"],
        "governs": ["TPA-106", "TPA-108(m)", "ICA-74"],
    }
    ids = {r["section_id"] for r in jurisdiction["reasons"]} | set(governing_law["governs"]) | set(governing_law["section_ids"])
    ids |= {s for f in findings for s in f["section_ids"]}
    ids |= {s["section_id"] for s in trace.steps if s["type"] == "verifier" and s["section_id"]}
    return {
        "id": "blr_flat", "task": "blr_flat",
        "title": "2BHK flat, Bengaluru (BBMP area), 11-month agreement",
        "status": "awaiting_approval", "created_at": START.isoformat(),
        "model": "stub built from backend tools (agent loop pending)",
        "agreement_text": task["agreement_text"],
        "facts": {"rent_per_month": facts["rent_per_month"], "deposit_inr": BLR_FINDINGS["C2"]["inputs"]["deposit"],
                  "built_year": facts["built_year"], "substantial_renovation_year": facts["substantial_renovation_year"],
                  "local_body": facts["local_body"], "premises_use": facts["premises_use"], "language": task["language"]},
        "governing_law": governing_law,
        "trace": trace.steps,
        "findings": findings,
        "drafts": [{"id": "d1", "tone": "request", "to": "Landlord",
                    "text": {lang: d["text"] for lang, d in drafts.items()}, "note": drafts["en"]["translation_note"]}],
        "sections": section_meta(ids),
        "max_tool_calls": 12, "not_a_lawyer": True, "notice": NOTICE,
    }


# Move-out reasons the model would write, keyed by clause; verdicts come from the task.
MOVEOUT_REASONS = {
    "C3": ("C3 allows painting only for tenant-caused damage with dated evidence, and the move-in checklist (E1) records scuffs and faded paint already present.", ["TPA-108(m)"]),
    "C2": ("C2 fixes a Rs 5,000 cleaning charge at move-out, and the claim matches the agreed amount.", []),
    "C4": ("C4 excludes reasonable wear and tear, and the move-in checklist (E2) records ordinary surface wear.", ["TPA-108(m)"]),
}


def build_moveout() -> dict[str, Any]:
    task = json.loads((TASKS / "moveout.json").read_text(encoding="utf-8"))
    deposit = 150000
    deductions = []
    for claim in task["claimed_deductions"]:
        reason, sections = MOVEOUT_REASONS[claim["clause_ref"]]
        deductions.append({"label": f"{claim['clause_ref']} {claim['label'].capitalize()}", "claimed_inr": claim["amount_inr"],
                           "verdict": claim["expected_verdict"], "reason": reason, "section_ids": sections})
    facts = task["facts"]
    return {
        "id": "moveout", "title": "Move-out, 2BHK flat, Bengaluru (BBMP area)", "status": "awaiting_approval",
        "facts": {"rent_per_month": facts["rent_per_month"], "deposit_inr": deposit, "built_year": facts["built_year"],
                  "substantial_renovation_year": None, "local_body": facts["local_body"],
                  "premises_use": facts["premises_use"], "language": task["language"]},
        "deposit_inr": deposit,
        "checklist": [{"date": e["date"], "item": f"{e['id']} {e['item'].capitalize()}", "condition": e["condition"], "evidence": e["evidence"]}
                      for e in task["move_in_checklist"]],
        "deductions": deductions,
        "next_steps": [
            {"title": "Written demand", "detail": "Send the approved challenge. Dhara records a follow-up 7 days later.", "certainty": "established"},
            {"title": "Legal notice", "detail": "If there is no refund, a firmer notice drafted from the same findings, preferably sent through an advocate.", "certainty": "established"},
            {"title": "Civil money-recovery suit", "detail": "The Rent Act does not apply here, so not the Rent Controller: a recovery suit in the Court of Small Causes, Bengaluru, within its pecuniary limit (limit unverified).", "certainty": "established"},
            {"title": "Consumer forum (e-Daakhil)", "detail": "Whether a tenancy deposit dispute is a consumer complaint is contested. Shown for completeness only.", "certainty": "uncertain"},
        ],
        "sections": section_meta({s for d in deductions for s in d["section_ids"]}),
        # The task as a POST /api/moveout body, for the intake page's sample button
        "sample_request": {"agreement_text": task["agreement_text"], "checklist": task["move_in_checklist"],
                           "deductions": [{k: v for k, v in d.items() if k != "expected_verdict"} for d in task["claimed_deductions"]],
                           "facts": task["facts"]},
        "not_a_lawyer": True, "notice": NOTICE,
    }


def build_blr_negotiation() -> dict[str, Any]:
    """The strict owner on three blr_flat clauses. Offers come from the task's move table and the letter from
    draft_message; only the tenant agent's decisions (what the model would say) are written here."""
    task = json.loads((TASKS / "blr_flat.json").read_text(encoding="utf-8"))
    persona, clause_ids = "strict_owner", ["C2", "C3", "C4"]
    first = landlord.opening(task, persona, clause_ids)
    round_1 = [
        Decision(clause_id="C2", decision="reject", section_id="ICA-74", verdict="cited",
                 reason="Forfeiting the whole deposit on any breach is a penalty; only reasonable compensation for actual loss is recoverable."),
        Decision(clause_id="C3", decision="counter", counter_terms={"lock_in_months": 3}, section_id="ICA-74", verdict="cited",
                 reason="Six months' rent on early exit is far above the likely loss; the tenant can accept a 3-month lock-in."),
        Decision(clause_id="C4", decision="reject", section_id="TPA-108(m)", verdict="cited",
                 reason="A flat Rs 15,000 ignores the exception for reasonable wear and tear."),
    ]
    second = landlord.respond(task, persona, round_1)
    round_2 = [
        Decision(clause_id="C2", decision="accept", reason="No forfeiture, and the refund within 30 days is within the tenant's limit.", verdict="unverified"),
        # The model accepted the 4-month lock-in; code flipped it because the tenant's limit is 3.
        Decision(clause_id="C3", decision="reject", reason="exceeds tenant limit: max_lock_in_months", verdict="unverified", limit_override=True),
        Decision(clause_id="C4", decision="accept", reason="Rs 8,000 is within the tenant's Rs 10,000 limit for exit painting.", verdict="unverified"),
    ]
    ask = BLR_FINDINGS["C3"]["ask"]
    negotiation = Negotiation(
        persona=persona, limits=TenantLimits(), status="stalled",
        rounds=[NegotiationRound(round=1, offers=first, decisions=round_1, model_ms=2140),
                NegotiationRound(round=2, offers=second, decisions=round_2, model_ms=1870)],
        agreed_terms={"C2": dict(second[0].terms), "C3": {"lock_in_months": 3, "ask": ask}, "C4": dict(second[2].terms)},
        settled_clauses=["C2", "C4"], open_clauses=["C3"])
    categories = [{"clause_ref": ref, "category": cat} for ref, cat in (("C2", "deposit_forfeiture"), ("C3", "lock_in"), ("C4", "painting_or_cleaning_fixed"))]
    items = letter_items(negotiation, categories)
    return {**negotiation.model_dump(),
            "agreed_letter": {lang: draft_message(items, "request", lang)["text"] for lang in ("en", "kn", "hi")},
            "sections": section_meta({"ICA-74", "TPA-108(m)"})}


def build_moveout_itemisation(moveout: dict[str, Any]) -> dict[str, Any]:
    """The landlord sent one number: Dhara asks for the itemised list before disputing anything."""
    claim, deposit, withheld = "painting and repairs 80396", 100000, 80396
    letter = {lang: itemisation_letter(deposit, withheld, claim, "C3", lang)["text"] for lang in ("en", "kn", "hi")}
    return {**{k: v for k, v in moveout.items() if k not in ("deductions", "sections")},
            "id": "moveout_itemisation", "status": "needs_itemisation", "deposit_inr": deposit,
            "facts": {**moveout["facts"], "deposit_inr": deposit}, "deductions": [], "drafts": [],
            "claimed_text": claim, "letter": letter,
            "itemisation": {"index": 0, "at": "", "type": "needs_itemisation", "reason": "the deductions are a single line",
                            "withheld_inr": withheld, "deposit_inr": deposit},
            "sections": section_meta({"ICA-74"})}


# Synthetic runs shipped with the scorer: one correct, one that cites the Model Tenancy Act cap.
SCORED_RUNS = [
    ("sample_run", "Correct run", "Right governing law, money within Rs 500, only sections from the law pack."),
    ("sample_run_wronglaw", "Wrong-law run", "Same findings, plus the claim that the law caps deposits at two months."),
]


TASK_LABEL = {"blr_flat": "Bengaluru flat", "pg_room": "PG room", "moveout": "Move-out"}


def clause_types() -> list[dict[str, Any]]:
    """Unfair or disputed clauses per category across the three test agreements (move-out: disputed deductions only)."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for name in ("blr_flat", "pg_room", "moveout"):
        task = json.loads((TASKS / f"{name}.json").read_text(encoding="utf-8"))
        if "claimed_deductions" in task:
            items = [(d["clause_ref"], d["category"], d["amount_inr"]) for d in task["claimed_deductions"] if d["expected_verdict"] == "disputed"]
        else:
            items = [(f["clause_ref"], f["category"], f["money_at_risk_inr"]) for f in task["expected"]["findings"]]
        for ref, category, amount in items:
            rows.setdefault(category, []).append({"task": TASK_LABEL[name], "clause_ref": ref, "amount_inr": amount})
    return sorted(({"category": c, "count": len(v), "clauses": v} for c, v in rows.items()), key=lambda r: (-r["count"], r["category"]))


def build_scores() -> dict[str, Any]:
    task = json.loads((TASKS / "blr_flat.json").read_text(encoding="utf-8"))
    forbidden = set(task["expected"]["forbidden_sections"])
    runs = []
    for name, label, summary in SCORED_RUNS:
        run = json.loads((TASKS / f"{name}.json").read_text(encoding="utf-8"))
        cited = [c["section_id"] for c in run.get("claims", []) if c.get("section_id")]
        cited += [s for f in run["findings"] for s in f["section_ids"]]
        runs.append({"id": name, "label": label, "summary": summary, "score": score(task, run),
                     "claims": run.get("claims", []), "forbidden_cited": sorted(set(cited) & forbidden)})
    return {
        "task": {"id": task["id"], "findings": len(task["expected"]["findings"]),
                 "money_max_inr": max(f["money_at_risk_inr"] for f in task["expected"]["findings"]),
                 "governing_law": task["expected"]["governing_law"], "forbidden_sections": sorted(forbidden)},
        "max_total": 3,
        "runs": runs,
        "sections": section_meta(forbidden | {"ICA-74", "TPA-106", "TPA-108(m)"}),
        "clause_types": clause_types(),
        # Live baseline-vs-agent results from python -m env.run_eval, when they exist
        "eval": json.loads((ROOT / "env" / "results" / "scores.json").read_text(encoding="utf-8"))
        if (ROOT / "env" / "results" / "scores.json").exists() else None,
    }


def write(name: str, data: dict[str, Any]) -> None:
    path = STUBS / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    write("blr_flat.json", build_blr_flat())
    write("blr_flat_negotiation.json", build_blr_negotiation())
    moveout_stub = build_moveout()
    write("moveout.json", moveout_stub)
    write("moveout_itemisation.json", build_moveout_itemisation(moveout_stub))
    write("scores.json", build_scores())
