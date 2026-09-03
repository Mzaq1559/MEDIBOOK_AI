"""
Tests for multi-key Groq client: round-robin distribution and
rate-limit failover across API keys.
"""

import unittest
from unittest.mock import patch, MagicMock, call

import app.groq_client as gc
from app.groq_client import LLMError


class _FakeRateLimitError(Exception):
    """Simulates the Groq SDK RateLimitError."""
    def __init__(self):
        super().__init__("Rate limit exceeded")
        self.status_code = 429


def _make_mock_response(content: str = '{"intent": "symptom"}'):
    """Build a mock Groq chat completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestMultiKeyRoundRobin(unittest.TestCase):
    """Verify requests distribute across multiple configured keys."""

    def setUp(self):
        # Reset the round-robin counter for each test
        import itertools, threading
        gc._key_counter_lock = threading.Lock()
        gc._key_counter = itertools.count()

    @patch("app.groq_client.settings")
    def test_two_keys_alternate(self, mock_settings):
        mock_settings.GROQ_API_KEYS = "key-aaa,key-bbb"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()
            client.chat.completions.create.return_value = _make_mock_response("response text")
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            gc.complete([{"role": "user", "content": "hi"}])
            gc.complete([{"role": "user", "content": "hi"}])
            gc.complete([{"role": "user", "content": "hi"}])
            gc.complete([{"role": "user", "content": "hi"}])

        self.assertEqual(keys_used, ["key-aaa", "key-bbb", "key-aaa", "key-bbb"])

    @patch("app.groq_client.settings")
    def test_three_keys_cycle(self, mock_settings):
        mock_settings.GROQ_API_KEYS = "k1,k2,k3"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()
            client.chat.completions.create.return_value = _make_mock_response("ok")
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            for _ in range(6):
                gc.complete([{"role": "user", "content": "x"}])

        self.assertEqual(keys_used, ["k1", "k2", "k3", "k1", "k2", "k3"])

    @patch("app.groq_client.settings")
    def test_single_key_backward_compat(self, mock_settings):
        """When only GROQ_API_KEY is set, all requests use that single key."""
        mock_settings.GROQ_API_KEYS = ""
        mock_settings.GROQ_API_KEY = "solo-key"
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()
            client.chat.completions.create.return_value = _make_mock_response("ok")
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            gc.complete([{"role": "user", "content": "x"}])
            gc.complete([{"role": "user", "content": "x"}])

        self.assertEqual(keys_used, ["solo-key", "solo-key"])


class TestRateLimitFailover(unittest.TestCase):
    """Verify rate-limit on one key triggers retry with a different key."""

    def setUp(self):
        import itertools, threading
        gc._key_counter_lock = threading.Lock()
        gc._key_counter = itertools.count()

    @patch("app.groq_client.settings")
    def test_rate_limit_switches_key(self, mock_settings):
        """Rate-limit on key-A must retry with key-B and succeed."""
        mock_settings.GROQ_API_KEYS = "key-A,key-B"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []
        call_count = {"n": 0}

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()

            def side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # First call (key-A) → rate limit
                    raise _FakeRateLimitError()
                # Second call (key-B) → success
                return _make_mock_response("recovered")

            client.chat.completions.create.side_effect = side_effect
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            result = gc.complete([{"role": "user", "content": "x"}], retries=3)

        self.assertEqual(result, "recovered")
        self.assertEqual(keys_used, ["key-A", "key-B"])

    @patch("app.groq_client.settings")
    def test_rate_limit_all_keys_raises_llm_error(self, mock_settings):
        """When all keys are rate-limited, LLMError is raised."""
        mock_settings.GROQ_API_KEYS = "key-A,key-B"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()
            client.chat.completions.create.side_effect = _FakeRateLimitError()
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            with self.assertRaises(LLMError):
                gc.complete([{"role": "user", "content": "x"}], retries=4)

        # With 2 keys and retries=4: A, B, A, B (4 attempts)
        self.assertEqual(len(keys_used), 4)
        self.assertEqual(keys_used, ["key-A", "key-B", "key-A", "key-B"])

    @patch("app.groq_client.settings")
    def test_single_key_rate_limit_raises(self, mock_settings):
        """Single key rate-limited → LLMError after all retries."""
        mock_settings.GROQ_API_KEYS = ""
        mock_settings.GROQ_API_KEY = "only-key"
        mock_settings.GROQ_MODEL = "test-model"

        def fake_client(api_key):
            client = MagicMock()
            client.chat.completions.create.side_effect = _FakeRateLimitError()
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            with self.assertRaises(LLMError):
                gc.complete([{"role": "user", "content": "x"}], retries=3)

    @patch("app.groq_client.settings")
    def test_non_rate_limit_error_also_advances_key(self, mock_settings):
        """Non-rate-limit errors also advance to the next key."""
        mock_settings.GROQ_API_KEYS = "key-A,key-B"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []
        call_count = {"n": 0}

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()

            def side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise ConnectionError("network down")
                return _make_mock_response("ok from B")

            client.chat.completions.create.side_effect = side_effect
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            result = gc.complete([{"role": "user", "content": "x"}], retries=3)

        self.assertEqual(result, "ok from B")
        self.assertEqual(keys_used, ["key-A", "key-B"])


class TestEmptyKeysConfig(unittest.TestCase):
    """Verify fallback when GROQ_API_KEYS is empty or not set."""

    def setUp(self):
        import itertools, threading
        gc._key_counter_lock = threading.Lock()
        gc._key_counter = itertools.count()

    @patch("app.groq_client.settings")
    def test_empty_keys_falls_back_to_single(self, mock_settings):
        mock_settings.GROQ_API_KEYS = ""
        mock_settings.GROQ_API_KEY = "fallback-key"
        mock_settings.GROQ_MODEL = "test-model"

        keys = gc._get_api_keys()
        self.assertEqual(keys, ["fallback-key"])

    @patch("app.groq_client.settings")
    def test_no_keys_at_all_raises(self, mock_settings):
        mock_settings.GROQ_API_KEYS = ""
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        with self.assertRaises(LLMError):
            gc.complete([{"role": "user", "content": "x"}])

    @patch("app.groq_client.settings")
    def test_comma_only_keys_ignored(self, mock_settings):
        mock_settings.GROQ_API_KEYS = ",,,"
        mock_settings.GROQ_API_KEY = "solo"
        mock_settings.GROQ_MODEL = "test-model"

        keys = gc._get_api_keys()
        self.assertEqual(keys, ["solo"])


class TestCompleteJsonMultiKey(unittest.TestCase):
    """Verify complete_json also distributes across keys."""

    def setUp(self):
        import itertools, threading
        gc._key_counter_lock = threading.Lock()
        gc._key_counter = itertools.count()

    @patch("app.groq_client.settings")
    def test_complete_json_distributes(self, mock_settings):
        mock_settings.GROQ_API_KEYS = "k1,k2"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.GROQ_MODEL = "test-model"

        keys_used = []

        def fake_client(api_key):
            keys_used.append(api_key)
            client = MagicMock()
            client.chat.completions.create.return_value = _make_mock_response('{"intent": "faq"}')
            return client

        with patch("app.groq_client._client", side_effect=fake_client):
            gc.complete_json([{"role": "user", "content": "x"}])
            gc.complete_json([{"role": "user", "content": "x"}])

        self.assertEqual(keys_used, ["k1", "k2"])


if __name__ == "__main__":
    unittest.main()
