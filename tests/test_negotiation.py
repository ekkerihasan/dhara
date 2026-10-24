import unittest

from housing import review_document
from housing.negotiation import negotiate


def deposit_review():
    review = review_document("Deposit is 6 months of rent.", "Karnataka", {"max_deposit_months": 2})
    review["preferences"] = {"max_deposit_months": 2}
    for finding in review["findings"]:
        finding.update(rule="max_deposit_months", limit=2, direction="maximum")
    return review


class NegotiationTests(unittest.TestCase):
    def test_compliant_offer_accepted_and_preserved(self):
        review = deposit_review()
        offer = "The deposit is 2 months of rent."
        result = negotiate(review, "C1", offer)
        self.assertEqual(result["decision"], "accept")
        self.assertEqual(result["proposed_revision"], offer)
        later = negotiate(review, "C1", "Deposit is 6 months.", result["history"])
        self.assertEqual(later["proposed_revision"], offer)
        self.assertEqual(len(later["history"]), 1)

    def test_conflict_countered(self):
        result = negotiate(deposit_review(), "C1", "Deposit is 4 months of rent.")
        self.assertEqual(result["decision"], "counter")
        self.assertIn("2", result["proposed_revision"])

    def test_omitted_or_ambiguous_units_never_accepted(self):
        for offer in ("Agreed.", "Deposit is reasonable.", "Deposit is two months.", "Deposit is INR 40000.", "Deposit is 2 months or 4 months."):
            self.assertEqual(negotiate(deposit_review(), "C1", offer)["decision"], "clarify", offer)

    def test_every_original_numeric_rule_must_be_resolved(self):
        review = review_document("Deposit is 6 months. Refund is within 90 days.", "Karnataka", {"max_deposit_months": 2, "max_refund_days": 30})
        # One original clause containing both preferences.
        review["clauses"] = [{"id": "C1", "text": "Deposit is 6 months. Refund is within 90 days."}]
        review["preferences"] = {"max_deposit_months": 2, "max_refund_days": 30}
        review["findings"] = [{"clause_id": "C1", "category": "preference", "rule": rule} for rule in review["preferences"]]
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months.")["decision"], "clarify")
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months. Refund is within 30 days.")["decision"], "accept")

    def test_generic_ambiguity_needs_clarification(self):
        review = deposit_review()
        review["findings"].append({"clause_id": "C1", "category": "ambiguity"})
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months.")["decision"], "clarify")

    def test_duplicate_normalization_and_history_not_mutated(self):
        review = deposit_review()
        history = negotiate(review, "C1", "Deposit is 4 months.")["history"]
        result = negotiate(review, "C1", "  DEPOSIT is  4 months. ", history)
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(len(history), 1)

    def test_three_offer_budget_is_per_clause(self):
        review = deposit_review()
        review["clauses"].append({"id": "C2", "text": "Deposit is 6 months."})
        review["findings"].append({"clause_id": "C2", "category": "preference", "rule": "max_deposit_months"})
        history = []
        for months in (6, 5, 4):
            history = negotiate(review, "C1", f"Deposit is {months} months.", history)["history"]
        result = negotiate(review, "C1", "Deposit is 2 months.", history)
        self.assertEqual(result["status"], "limit_reached")
        self.assertEqual(len(result["history"]), 3)
        self.assertEqual(negotiate(review, "C2", "Deposit is 2 months.", history)["decision"], "accept")

    def test_legal_findings_require_human(self):
        review = deposit_review()
        review["findings"][0]["category"] = "legal"
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months.")["decision"], "escalate")

    def test_offer_cannot_introduce_conditional_legal_conflict(self):
        facts = {"city": "Bengaluru", "residential": True, "ownership_type": "private",
                 "building_age_years": 25, "tenancy_date": "2026-10-01", "schedule_area": "part_a",
                 "standard_rent_monthly": 3000, "other_exemptions_checked": True}
        review = review_document("Deposit is 6 months of rent.", "Karnataka", {"max_deposit_months": 2}, facts)
        result = negotiate(review, "C1", "Deposit is 2 months of rent. Landlord may disconnect electricity to compel departure.")
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(result["status"], "human_review")

    def test_satisfied_original_terms_cannot_disappear(self):
        review = review_document("Deposit is 6 months. Refund is within 30 days.", "Karnataka", {"max_deposit_months": 2, "max_refund_days": 30})
        review["clauses"][0]["text"] = "Deposit is 6 months. Refund is within 30 days."
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months.")["decision"], "clarify")
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months. Refund within 60 days.")["decision"], "counter")
        self.assertEqual(negotiate(review, "C1", "Deposit is 2 months. Refund within 30 days.")["decision"], "accept")

    def test_messages_remove_only_accepted_findings_and_keep_agreements(self):
        review = review_document("1. Deposit is 6 months.\n2. Termination notice is 90 days.", "Karnataka", {"max_deposit_months": 2, "max_notice_days": 30})
        first = negotiate(review, "C1", "Deposit is 2 months.")
        self.assertNotIn("- C1:", first["messages"]["english"])
        self.assertIn("- C2:", first["messages"]["english"])
        second = negotiate(review, "C2", "Termination notice is 30 days.", first["history"])
        self.assertEqual(len(second["messages"]["agreements_original"]), 2)
        self.assertEqual(second["messages"]["agreements_original"][0]["text"], "Deposit is 2 months.")
        self.assertNotIn("- C2:", second["messages"]["english"])
        repeated = negotiate(review, "C1", "Deposit is 9 months.", second["history"])
        self.assertEqual(repeated["messages"]["agreements_original"], second["messages"]["agreements_original"])


if __name__ == "__main__":
    unittest.main()
