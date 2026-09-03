"""
Regression tests for the medical history extraction pipeline:
  Layer 1: extract_medical_history() correctly parses allergies, conditions, past issues
  Layer 2: build_patient_summary() includes all extracted fields

Allergy extraction must handle ALL of these phrasing patterns:
  - "peanuts and eggs" (and-joined, 2 items)
  - "peanuts, butter, eggs" (comma-separated, 3+ items)
  - "peanuts, butter, and eggs" (mixed comma + and)
  - "peanuts" (single allergy)
"""

import unittest


class TestAllergyExtractionPatterns(unittest.TestCase):
    """Verify all 4 required allergy phrasing patterns produce individual items."""

    def test_and_joined_two_items(self):
        """'peanuts and eggs' → two separate items."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("i am allergic to peanuts and eggs")
        self.assertEqual(result["allergies"], ["peanuts", "eggs"])

    def test_comma_separated_three_items(self):
        """'peanuts, butter, eggs' → three separate items."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("im allergic to peanuts, butter, eggs")
        self.assertEqual(result["allergies"], ["peanuts", "butter", "eggs"])

    def test_mixed_comma_and(self):
        """'peanuts, butter, and eggs' → three separate items (Oxford comma)."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("im allergic to peanuts, butter, and eggs")
        self.assertEqual(result["allergies"], ["peanuts", "butter", "eggs"])

    def test_single_allergy(self):
        """'peanuts' → one item."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("im allergic to peanuts")
        self.assertEqual(result["allergies"], ["peanuts"])

    def test_single_allergy_penicillin(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("I am allergic to penicillin")
        self.assertEqual(result["allergies"], ["penicillin"])

    def test_comma_separated_with_period(self):
        """Sentence with period terminator still captures all items."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("allergic to peanuts, butter, and eggs. I also have diabetes")
        self.assertEqual(result["allergies"], ["peanuts", "butter", "eggs"])
        self.assertIn("diabetes", result["conditions"])

    def test_shellfish_and_nuts_with_period(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("allergic to shellfish and nuts.")
        self.assertEqual(sorted(result["allergies"]), ["nuts", "shellfish"])

    def test_intolerant_two_items(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("intolerant to lactose and gluten")
        self.assertEqual(result["allergies"], ["lactose", "gluten"])

    def test_allergy_colon_format(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("allergy: penicillin")
        self.assertEqual(result["allergies"], ["penicillin"])

    def test_allergies_plural_format(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("I have allergies to pollen")
        self.assertEqual(result["allergies"], ["pollen"])

    def test_multiple_allergy_sentences(self):
        """Two separate 'allergic to' mentions in one message."""
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("I am allergic to shellfish. Also allergic to peanuts and eggs")
        self.assertIn("shellfish", result["allergies"])
        self.assertIn("peanuts", result["allergies"])
        self.assertIn("eggs", result["allergies"])

    def test_no_allergies_mentioned(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("nothing special")
        self.assertEqual(result["allergies"], [])


class TestConditionsAndPastIssues(unittest.TestCase):
    """Verify condition and past issue extraction."""

    def test_conditions_diabetes(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("I have diabetes and high blood pressure")
        self.assertIn("diabetes", result["conditions"])
        self.assertIn("high blood pressure", result["conditions"])

    def test_conditions_asthma(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("I have asthma")
        self.assertIn("asthma", result["conditions"])

    def test_past_issues(self):
        from app.chatbot_handlers import extract_medical_history
        result = extract_medical_history("had pneumonia last year")
        self.assertTrue(len(result["past_issues"]) > 0)

    def test_raw_preserved(self):
        from app.chatbot_handlers import extract_medical_history
        text = "i am allergic to peanuts and eggs"
        result = extract_medical_history(text)
        self.assertEqual(result["raw"], text)


class TestPatientSummary(unittest.TestCase):
    """Verify build_patient_summary renders extracted history."""

    def test_summary_includes_split_allergies(self):
        """Summary should list each allergy separately."""
        from app.chatbot_handlers import build_patient_summary
        history = {
            "conditions": ["diabetes"],
            "allergies": ["peanuts", "butter", "eggs"],
            "past_issues": [],
        }
        summary = build_patient_summary("headache", "normal", history)
        self.assertIn("peanuts", summary)
        self.assertIn("butter", summary)
        self.assertIn("eggs", summary)
        self.assertIn("diabetes", summary)

    def test_summary_no_history(self):
        from app.chatbot_handlers import build_patient_summary
        summary = build_patient_summary("headache", "normal", None)
        self.assertIn("headache", summary)
        self.assertNotIn("allergies", summary.lower())


if __name__ == "__main__":
    unittest.main()
