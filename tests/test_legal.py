import unittest

from housing import review_document
from housing.legal import screen_jurisdiction


class KarnatakaApplicabilityTests(unittest.TestCase):
    def facts(self, **overrides):
        return {"city": "Bengaluru", "residential": True, "ownership_type": "private",
                "building_age_years": 25, "tenancy_date": "2026-10-01",
                "schedule_area": "part_a", "standard_rent_monthly": 3000,
                "other_exemptions_checked": True, **overrides}

    def test_market_rent_does_not_establish_statutory_rent(self):
        facts = self.facts(monthly_rent=20000)
        del facts["standard_rent_monthly"]
        result = screen_jurisdiction("Karnataka", facts)
        self.assertEqual(result["status"], "applicability_unresolved")
        self.assertFalse(result["conditional_rules_enabled"])
        self.assertTrue(any("standard rent" in question for question in result["questions"]))

    def test_exclusions_and_threshold_boundaries(self):
        for override in ({"ownership_type": "government"}, {"building_age_years": 14},
                         {"standard_rent_monthly": 3501}, {"schedule_area": "other_scheduled", "standard_rent_monthly": 2001}):
            self.assertEqual(screen_jurisdiction("Karnataka", self.facts(**override))["status"], "rent_act_excluded")
        for rent in (3000, 3500):
            self.assertEqual(screen_jurisdiction("Karnataka", self.facts(standard_rent_monthly=rent))["status"], "conditional_legal_review")

    def test_missing_or_unconfirmed_facts_do_not_enable_rules(self):
        for key in self.facts():
            facts = self.facts()
            del facts[key]
            self.assertFalse(screen_jurisdiction("Karnataka", facts)["conditional_rules_enabled"], key)
        self.assertFalse(screen_jurisdiction("Karnataka", self.facts(residential=False))["conditional_rules_enabled"])

    def test_service_rule_is_conditional_and_cited(self):
        text = "1. The landlord may disconnect electricity to force the tenant to leave."
        self.assertEqual(review_document(text, "Karnataka")["findings"], [])
        result = review_document(text, "Karnataka", facts=self.facts())
        self.assertEqual(result["status"], "conditional_legal_review")
        finding = result["findings"][0]
        self.assertEqual(finding["category"], "potential_legal_conflict")
        self.assertEqual(finding["citations"][0]["section"], "49(1)")
        self.assertIn("conditional", finding["applicability"])
        self.assertEqual(review_document(text, "Karnataka", facts=self.facts(building_age_years=2))["findings"], [])

    def test_existing_prohibition_is_not_flagged(self):
        result = review_document("1. The landlord shall not disconnect electricity without lawful cause.", "Karnataka", facts=self.facts())
        self.assertEqual(result["findings"], [])

    def test_invalid_facts_rejected(self):
        for facts in ({"monthly_rent": -1}, {"building_age_years": float("nan")}, {"residential": "yes"}, {"tenancy_date": "yesterday"}):
            with self.assertRaises(ValueError):
                screen_jurisdiction("Karnataka", facts)


if __name__ == "__main__":
    unittest.main()
