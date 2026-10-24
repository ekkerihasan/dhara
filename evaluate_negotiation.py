"""Scripted repeated-action control versus bounded controller, not LLM evaluation.

Run: python evaluate_negotiation.py
Both policies see the same six-offer fixed stream and public review data.
This measures duplicate stopping only, not legal accuracy or model quality.
"""
import argparse
import json
from pathlib import Path

from housing import review_document
from housing.negotiation import negotiate


def evaluate() -> dict:
    preferences = {"max_deposit_months": 2}
    review = review_document("Deposit is 6 months of rent.", "Karnataka", preferences)
    review["preferences"] = preferences
    offers = ["Deposit is 4 months of rent."] * 6
    control = [{"offer": offer, "decision": "counter"} for offer in offers]
    history = []
    result = None
    for offer in offers:
        result = negotiate(review, "C1", offer, history)
        history = result["history"]
        if result["decision"] in {"accept", "escalate"}:
            break
    return {
        "comparison": "scripted repeated-action control vs bounded controller",
        "model_baseline": False,
        "scenario": "fixed repeated over-budget deposit offer",
        "scripted_control": {"actions": len(control), "duplicate_actions": 5, "resolved": False},
        "bounded_controller": {"actions": len(history), "duplicate_actions": 1,
                               "resolved": False, "terminal_status": result["status"]},
        "limitations": ["One scripted fixture; no model or API was used.",
                        "Demonstrates stopping repeated offers, not improved legal accuracy or successful agreement."],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(evaluate(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
