import json
from pathlib import Path
import tempfile
import unittest

from housing import ActionGuard, extract_clauses, extract_document, review_document


class HousingReviewTests(unittest.TestCase):
    def test_missing_and_unsupported_jurisdiction_never_claim_illegality(self):
        for state, expected in [("", "needs_jurisdiction"), ("Delhi", "unsupported_jurisdiction"), ("Karnataka", "applicability_unresolved")]:
            result = review_document("1. Deposit is 6 months of rent.", state, {"max_deposit_months": 2})
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["findings"][0]["category"], "preference")
            self.assertEqual(result["findings"][0]["citations"], [])
            self.assertFalse(result["sources"][0]["applicable"])
            json.dumps(result, ensure_ascii=False)

    def test_clause_references_and_continuations(self):
        clauses = extract_clauses("1. Rent is due monthly.\nContinued term.\n2. Notice is 30 days.\f3. Deposit is refundable.")
        self.assertEqual(len(clauses), 3)
        self.assertIn("Continued term", clauses[0]["text"])
        self.assertEqual((clauses[1]["page"], clauses[1]["line"]), (1, 3))
        self.assertEqual(clauses[2]["page"], 2)

    def test_preferences_are_explicit_and_clean_terms_pass(self):
        text = "1. Deposit is 6 months of rent.\n2. Notice is 30 days.\n3. Annual rent increase is 5%."
        self.assertEqual(review_document(text)["findings"], [])
        result = review_document(text, "Karnataka", {"max_deposit_months": 6, "max_notice_days": 30, "max_rent_increase_percent": 5})
        self.assertEqual(result["findings"], [])
        result = review_document(text, preferences={"max_deposit_months": 2, "max_notice_days": 20, "max_rent_increase_percent": 3})
        self.assertEqual(len(result["findings"]), 3)
        self.assertTrue(all(f["category"] == "preference" for f in result["findings"]))

    def test_uncertain_numbers_do_not_become_definite_findings(self):
        result = review_document("Deposit is six months of rent.", preferences={"max_deposit_months": 2})
        self.assertEqual(result["findings"][0]["category"], "ambiguity")
        result = review_document("Notice is 30 days or 60 days.", preferences={"max_notice_days": 30})
        self.assertEqual(result["findings"][0]["category"], "ambiguity")

    def test_limits_and_duplicate_guard(self):
        guard = ActionGuard(3)
        self.assertTrue(guard.allow("Negotiate", "C1"))
        self.assertFalse(guard.allow(" negotiate ", "C1"))
        self.assertTrue(guard.allow("negotiate", "C2"))
        self.assertFalse(guard.allow("negotiate", "C3"))
        result = review_document("\n".join(f"{i}. Rent payable monthly." for i in range(1, 70)))
        self.assertTrue(any(t["status"] == "action_limit_reached" for t in result["trace"]))

    def test_invalid_preferences_rejected(self):
        for prefs in [{"max_deposit_months": -1}, {"max_notice_days": float("nan")}, {"max_notice_days": True}, {"law": "MTA"}]:
            with self.assertRaises(ValueError):
                review_document("text", preferences=prefs)

    def test_minimum_preferences_and_refund(self):
        result = review_document("1. Termination notice is 10 days.\n2. Entry requires 2 hours notice.\n3. Deposit refund is due in 60 days.", preferences={"min_notice_days": 30, "min_entry_notice_hours": 24, "max_refund_days": 30})
        self.assertTrue(any("falls below" in f["explanation"] for f in result["findings"]))
        self.assertTrue(any("refund deadline" in f["explanation"] for f in result["findings"]))
        self.assertEqual(sum(t["action"] == "review_clause" for t in result["trace"]), 3)

    def test_termination_notice_does_not_apply_to_access(self):
        for text in ["Landlord may enter without notice.", "Inspection requires 48 hours notice.", "Access requires 2 days notice."]:
            result = review_document(text, preferences={"max_notice_days": 30, "min_notice_days": 30})
            self.assertFalse(any("notice period" in f["proposed_revision"] for f in result["findings"]))
        result = review_document("Entry requires 2 days notice. Termination requires 60 days notice.", preferences={"max_notice_days": 30})
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["category"], "preference")
        self.assertIn("60 days", result["findings"][0]["explanation"])

    def test_empty_document_and_language_limit_are_explicit(self):
        result = review_document("")
        self.assertIn("Provide readable agreement text.", result["questions"])
        self.assertIn("template", result["messages"]["translation_note"].lower())
        self.assertIn("hindi", result["messages"])

    def test_text_file_extraction_and_unsupported_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lease.txt"
            path.write_text("1. Monthly rent.", encoding="utf-8")
            self.assertEqual(extract_document(path), "1. Monthly rent.")
            unsupported = Path(directory) / "archive.zip"
            unsupported.write_bytes(b"not a supported document")
            with self.assertRaisesRegex(ValueError, "Supported files"):
                extract_document(unsupported)


if __name__ == "__main__":
    unittest.main()
