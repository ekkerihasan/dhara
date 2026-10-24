"""Reproducible offline fixture checks, not an LLM baseline comparison."""
import argparse
import json
from pathlib import Path

from housing import review_document


CASES = [
    {"name": "deposit_conflict", "text": "1. Deposit is 6 months of rent.",
     "state": "Karnataka", "preferences": {"max_deposit_months": 2}, "expected": {"C1"}},
    {"name": "clean_deposit", "text": "1. Deposit is 2 months of rent.",
     "state": "Karnataka", "preferences": {"max_deposit_months": 2}, "expected": set()},
    {"name": "notice_conflict", "text": "1. Termination notice is 90 days.",
     "state": "Karnataka", "preferences": {"max_notice_days": 30}, "expected": {"C1"}},
    {"name": "clean_notice", "text": "1. Termination notice is 30 days.",
     "state": "Karnataka", "preferences": {"max_notice_days": 30}, "expected": set()},
    {"name": "ambiguous_entry", "text": "1. Landlord may enter without notice.",
     "state": "Karnataka", "preferences": {}, "expected": {"C1"}},
    {"name": "missing_jurisdiction", "text": "1. Rent is payable monthly.",
     "state": "", "preferences": {}, "expected": set(), "status": "needs_jurisdiction"},
    {"name": "unsupported_jurisdiction", "text": "1. Rent is payable monthly.",
     "state": "Delhi", "preferences": {}, "expected": set(), "status": "unsupported_jurisdiction"},
    {"name": "unknown_deposit_number", "text": "1. Deposit is six months of rent.",
     "state": "Karnataka", "preferences": {"max_deposit_months": 2}, "expected": {"C1"}},
]


def evaluate():
    rows = []
    true_positive = false_positive = false_negative = 0
    for case in CASES:
        result = review_document(case["text"], case["state"], case["preferences"])
        predicted = {finding["clause_id"] for finding in result["findings"]}
        expected = case["expected"]
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
        expected_status = case.get("status", "applicability_unresolved")
        no_legal_claim = all(f["category"] != "legal" and not f["citations"] for f in result["findings"])
        rows.append({"case": case["name"], "expected_clause_ids": sorted(expected),
                     "flagged_clause_ids": sorted(predicted), "status": result["status"],
                     "passed": predicted == expected and result["status"] == expected_status and no_legal_claim})
    return {"evaluation": "offline development fixtures", "cases": len(rows),
            "passed": sum(row["passed"] for row in rows),
            "clause_precision": true_positive / (true_positive + false_positive) if true_positive + false_positive else None,
            "clause_recall": true_positive / (true_positive + false_negative) if true_positive + false_negative else None,
            "limitations": ["Small synthetic development set, not held-out evidence of real-world accuracy.",
                            "Measures flagged clause IDs and jurisdiction status, not legal correctness.",
                            "No live baseline/new-agent comparison or claimed model improvement."], "results": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
