"""
Regression tests for LLM resilience fixes:
  FIX 1 — JSON retry in complete_json()
  FIX 2 — Regex fallback entity extraction when LLM fails
  FIX 3 — Per-key rate limiter
  FIX 4 — Reduced NLU history token usage
"""

import itertools
import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call

import app.groq_client as gc
from app.groq_client import LLMError
from app.chatbot_state import S


def _reset_key_counter():
    gc._key_counter_lock = threading.Lock()
    gc._key_counter = itertools.count()


def _reset_rate_limiter():
    gc._rate_lock = threading.Lock()
    gc._key_request_times = {}


def _make_mock_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ──────────────────────────────────────────────────────────────────────
# FIX 1 — complete_json() retries on malformed JSON
# ──────────────────────────────────────────────────────────────────────
class TestFix1_JsonRetry(unittest.TestCase):

    def setUp(self):
        _reset_key_counter()
        _reset_rate_limiter()

    @patch("app.groq_client.settings")
    def test_json_retry_succeeds_on_second_attempt(self, mock_settings):
        """First call returns bad JSON, second returns valid JSON."""
        mock_settings.GROQ_API_KEYS = "k1"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test"

        call_count = {"n": 0}

        def fake_complete(messages, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "not valid json {{{"
            return '{"intent": "faq"}'

        with patch("app.groq_client.complete", side_effect=fake_complete):
            result = gc.complete_json([{"role": "user", "content": "x"}])

        self.assertEqual(result, {"intent": "faq"})
        self.assertEqual(call_count["n"], 2)

    @patch("app.groq_client.settings")
    def test_json_retry_exhausted_raises(self, mock_settings):
        """All attempts return bad JSON → LLMError."""
        mock_settings.GROQ_API_KEYS = "k1"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test"

        def fake_complete(messages, **kwargs):
            return "broken json"

        with patch("app.groq_client.complete", side_effect=fake_complete):
            with self.assertRaises(LLMError):
                gc.complete_json(
                    [{"role": "user", "content": "x"}],
                    json_retries=2,
                )

    @patch("app.groq_client.settings")
    def test_json_non_dict_raises(self, mock_settings):
        """Valid JSON but not a dict (e.g. a list) → LLMError."""
        mock_settings.GROQ_API_KEYS = "k1"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test"

        def fake_complete(messages, **kwargs):
            return "[1, 2, 3]"

        with patch("app.groq_client.complete", side_effect=fake_complete):
            with self.assertRaises(LLMError):
                gc.complete_json([{"role": "user", "content": "x"}])

    @patch("app.groq_client.settings")
    def test_llm_error_propagates_immediately(self, mock_settings):
        """LLMError from complete() is NOT retried by json_retries."""
        mock_settings.GROQ_API_KEYS = "k1"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test"

        call_count = {"n": 0}

        def fake_complete(messages, **kwargs):
            call_count["n"] += 1
            raise LLMError("rate limited")

        with patch("app.groq_client.complete", side_effect=fake_complete):
            with self.assertRaises(LLMError):
                gc.complete_json(
                    [{"role": "user", "content": "x"}],
                    json_retries=2,
                )

        # complete() was called only once — LLMError is not retried
        self.assertEqual(call_count["n"], 1)


# ──────────────────────────────────────────────────────────────────────
# FIX 2 — Regex fallback entity extraction when LLM fails
# ──────────────────────────────────────────────────────────────────────
class TestFix2_FallbackEntities(unittest.TestCase):

    def test_fallback_specialty_heart_ache(self):
        from app.chatbot_nlu import _fallback_specialty
        self.assertEqual(_fallback_specialty("heart ache"), "Cardiologist")

    def test_fallback_specialty_rashes(self):
        from app.chatbot_nlu import _fallback_specialty
        self.assertEqual(_fallback_specialty("rashes on my skin"), "Dermatologist")

    def test_fallback_specialty_no_match(self):
        from app.chatbot_nlu import _fallback_specialty
        self.assertIsNone(_fallback_specialty("hello"))

    def test_fallback_doctor_name_dr_smith(self):
        from app.chatbot_nlu import _fallback_doctor_name
        result = _fallback_doctor_name("I want to see Dr. Smith")
        self.assertIn("Smith", result)

    def test_fallback_doctor_name_dr_fatima(self):
        from app.chatbot_nlu import _fallback_doctor_name
        result = _fallback_doctor_name("book with Dr Fatima")
        self.assertIn("Fatima", result)

    def test_fallback_doctor_name_no_match(self):
        from app.chatbot_nlu import _fallback_doctor_name
        self.assertIsNone(_fallback_doctor_name("hello world"))

    def test_fallback_date_today(self):
        from app.chatbot_nlu import _fallback_date
        self.assertEqual(_fallback_date("I need an appointment today"), "today")

    def test_fallback_date_tomorrow(self):
        from app.chatbot_nlu import _fallback_date
        self.assertEqual(_fallback_date("book for tomorrow"), "tomorrow")

    def test_fallback_date_iso(self):
        from app.chatbot_nlu import _fallback_date
        self.assertEqual(_fallback_date("on 2026-09-15"), "2026-09-15")

    def test_fallback_date_natural(self):
        from app.chatbot_nlu import _fallback_date
        result = _fallback_date("Sept 3")
        self.assertIsNotNone(result)
        self.assertIn("Sep", result)

    def test_fallback_date_urdu_aaj(self):
        from app.chatbot_nlu import _fallback_date
        self.assertEqual(_fallback_date("mujhe aaj appointment chahiye"), "today")

    def test_fallback_date_no_match(self):
        from app.chatbot_nlu import _fallback_date
        self.assertIsNone(_fallback_date("hello"))

    def test_classify_with_llm_failure_extracts_specialty(self):
        """When LLM fails, classify() should still extract specialty from text."""
        from app.chatbot_nlu import classify

        with patch("app.groq_client.complete_json", side_effect=Exception("rate limit")):
            result = classify("heart ache", [], S.IDLE)

        self.assertEqual(result["specialty"], "Cardiologist")
        self.assertEqual(result["intent"], "symptom")

    def test_classify_with_llm_failure_extracts_doctor_name(self):
        """When LLM fails, classify() should still extract doctor name."""
        from app.chatbot_nlu import classify

        with patch("app.groq_client.complete_json", side_effect=Exception("rate limit")):
            result = classify("I want to see Dr. Ahmed", [], S.IDLE)

        self.assertIn("Ahmed", result["doctor_name"] or "")

    def test_classify_with_llm_failure_extracts_date(self):
        """When LLM fails, classify() should still extract date."""
        from app.chatbot_nlu import classify

        with patch("app.groq_client.complete_json", side_effect=Exception("rate limit")):
            result = classify("book for tomorrow", [], S.IDLE)

        self.assertEqual(result["date"], "tomorrow")

    def test_classify_with_llm_success_no_fallback(self):
        """When LLM succeeds, fallback extractors should NOT override LLM results."""
        from app.chatbot_nlu import classify

        with patch("app.groq_client.complete_json", return_value={
            "intent": "appointment",
            "specialty": "ENT Specialist",
            "doctor_name": "Dr. Zain",
            "date": None,
        }):
            result = classify("heart ache", [], S.IDLE)

        # LLM's specialty should be preserved, not overridden by fallback
        self.assertEqual(result["specialty"], "ENT Specialist")


# ──────────────────────────────────────────────────────────────────────
# FIX 3 — Per-key rate limiter
# ──────────────────────────────────────────────────────────────────────
class TestFix3_RateLimiter(unittest.TestCase):

    def setUp(self):
        _reset_key_counter()
        _reset_rate_limiter()

    def test_rate_limiter_no_pause_under_limit(self):
        """Under 25 RPM → no sleep calls."""
        with patch("app.groq_client.time.sleep") as mock_sleep:
            for _ in range(10):
                gc._rate_limit_wait(0)
            mock_sleep.assert_not_called()

    def test_rate_limiter_pauses_at_limit(self):
        """At 25 RPM → sleep is called on the 26th request."""
        # Inject 25 recent timestamps
        gc._key_request_times[0] = [time.monotonic() for _ in range(25)]

        with patch("app.groq_client.time.sleep") as mock_sleep:
            gc._rate_limit_wait(0)
            mock_sleep.assert_called_once()

    def test_rate_limiter_independent_per_key(self):
        """Key 0 at limit doesn't affect key 1."""
        gc._key_request_times[0] = [time.monotonic() for _ in range(25)]

        with patch("app.groq_client.time.sleep") as mock_sleep:
            gc._rate_limit_wait(1)  # different key
            mock_sleep.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# FIX 4 — Reduced NLU history token usage
# ──────────────────────────────────────────────────────────────────────
class TestFix4_HistoryTrim(unittest.TestCase):

    def test_classify_uses_4_turns_not_8(self):
        """Verify history_blob only includes last 4 messages."""
        from app.chatbot_nlu import _NLU_HISTORY_TURNS
        self.assertEqual(_NLU_HISTORY_TURNS, 4)

    def test_classify_with_long_history_succeeds(self):
        """classify() should work with more than 4 history messages."""
        from app.chatbot_nlu import classify
        from app.schemas import MessageItem

        history = [
            MessageItem(role="user", message=f"msg {i}", timestamp="2026-09-01T00:00:00Z")
            for i in range(20)
        ]

        with patch("app.groq_client.complete_json", return_value={
            "intent": "symptom", "specialty": None,
        }):
            result = classify("headache", history, S.IDLE)

        self.assertEqual(result["intent"], "symptom")


if __name__ == "__main__":
    unittest.main()
