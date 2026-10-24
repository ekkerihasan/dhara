import unittest

from housing.messages import draft_messages


class MessageTests(unittest.TestCase):
    def test_numeric_rules_preserve_values_and_units(self):
        rules = ["max_deposit_months", "max_notice_days", "min_notice_days", "max_rent_increase_percent", "max_refund_days", "min_entry_notice_hours"]
        for rule in rules:
            result = draft_messages([{"clause_id": "C7", "category": "preference", "rule": rule, "limit": 2.5}])
            for language in ("english", "kannada", "hindi"):
                self.assertIn("2.5", result[language])
                self.assertIn("C7", result[language])
            self.assertNotIn("Please", result["kannada"])
            self.assertNotIn("Please", result["hindi"])

    def test_minimum_and_maximum_differ(self):
        minimum = draft_messages([{"clause_id": "C1", "category": "preference", "rule": "min_notice_days", "limit": 30}])
        maximum = draft_messages([{"clause_id": "C1", "category": "preference", "rule": "max_notice_days", "limit": 30}])
        self.assertIn("at least 30", minimum["english"])
        self.assertIn("no more than 30", maximum["english"])
        self.assertNotEqual(minimum["kannada"], maximum["kannada"])

    def test_arbitrary_prose_and_legal_text_not_fake_translated(self):
        findings = [{"clause_id": "C2", "category": "ambiguity", "proposed_revision": "ARBITRARY WORDING"}, {"clause_id": "C3", "category": "legal", "explanation": "INVENTED SECTION"}]
        result = draft_messages(findings, [{"clause_id": "C4", "text": "Original negotiated wording"}])
        for language in ("english", "kannada", "hindi"):
            self.assertNotIn("ARBITRARY", result[language])
            self.assertNotIn("INVENTED", result[language])
            self.assertNotIn("Original negotiated", result[language])
        self.assertEqual(result["agreements_original"][0]["text"], "Original negotiated wording")
        self.assertIn("not free-form translation", result["translation_note"])

    def test_empty_findings_all_languages(self):
        result = draft_messages([])
        self.assertTrue(all(result[language] for language in ("english", "kannada", "hindi")))


if __name__ == "__main__":
    unittest.main()
