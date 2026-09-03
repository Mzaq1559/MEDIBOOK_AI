"""Groq LLM client. Model ID comes only from GROQ_MODEL. Secrets are never logged."""

from __future__ import annotations

import itertools
import json
import logging
import threading
import time
from typing import Any, Optional

from groq import Groq

from app.config import settings

logger = logging.getLogger("medibook.ai.groq")

LLM_FALLBACK = "Please try again or contact our team"


class LLMError(Exception):
    """Raised when the Groq API call fails after retries."""


# ── Multi-key pool ───────────────────────────────────────────────────
_key_counter_lock = threading.Lock()
_key_counter = itertools.count()

# ── Per-key rate limiter ────────────────────────────────────────────────
# Tracks timestamps of recent requests per key index to stay under
# ~25 RPM (leaving headroom below Groq's 30 RPM free-tier limit).
_RATE_LIMIT_RPM = 25
_RATE_LIMIT_WINDOW = 60.0  # seconds
_key_request_times: dict[int, list[float]] = {}
_rate_lock = threading.Lock()


def _rate_limit_wait(key_idx: int) -> None:
    """Block briefly if the given key has exceeded _RATE_LIMIT_RPM in the
    last 60-second window.  Returns immediately if under the limit."""
    now = time.monotonic()
    with _rate_lock:
        times = _key_request_times.setdefault(key_idx, [])
        # Purge entries older than the window
        cutoff = now - _RATE_LIMIT_WINDOW
        _key_request_times[key_idx] = [t for t in times if t > cutoff]
        times = _key_request_times[key_idx]
        if len(times) >= _RATE_LIMIT_RPM:
            wait_for = times[0] - cutoff + 0.5  # wait until oldest exits the window
            logger.info(
                "Rate limiter: key %s at %s RPM, pausing %.1fs",
                key_idx + 1, len(times), wait_for,
            )
            time.sleep(max(0.1, wait_for))
        _key_request_times[key_idx].append(time.monotonic())


def _get_api_keys() -> list[str]:
    """Return the list of configured API keys.

    Priority: GROQ_API_KEYS (comma-separated) > GROQ_API_KEY (single).
    """
    multi = [k.strip() for k in (settings.GROQ_API_KEYS or "").split(",") if k.strip()]
    if multi:
        return multi
    single = (settings.GROQ_API_KEY or "").strip()
    if single:
        return [single]
    return []


def _next_key() -> str:
    """Return the next API key via round-robin.  Thread-safe."""
    keys = _get_api_keys()
    if not keys:
        raise LLMError(LLM_FALLBACK)
    with _key_counter_lock:
        idx = next(_key_counter)
    return keys[idx % len(keys)]


def _client(api_key: str) -> Groq:
    return Groq(api_key=api_key)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect Groq SDK rate-limit errors by class name or status code."""
    name = type(exc).__name__
    if "RateLimit" in name:
        return True
    status = getattr(exc, "status_code", None)
    return status == 429


def complete(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    json_mode: bool = False,
    retries: int = 3,
) -> str:
    """Call Groq chat completions. Returns assistant text. Never logs API keys.

    Distributes load across multiple API keys via round-robin.  On a
    RateLimitError the next attempt uses a *different* key so that a
    rate-limited account does not consume the remaining retry budget.
    """
    keys = _get_api_keys()
    if not keys:
        raise LLMError(LLM_FALLBACK)

    last_error: Optional[Exception] = None
    create_kwargs: dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        create_kwargs["response_format"] = {"type": "json_object"}

    # Pick the starting key via round-robin
    with _key_counter_lock:
        start_idx = next(_key_counter)
    key_idx = start_idx

    for attempt in range(1, retries + 1):
        current_key = keys[key_idx % len(keys)]
        # Per-key rate limiter: pause if this key is near its RPM ceiling
        _rate_limit_wait(key_idx % len(keys))
        try:
            client = _client(current_key)
            response = client.chat.completions.create(**create_kwargs)
            choice = response.choices[0].message
            content = (choice.content or "").strip()
            if not content:
                raise LLMError("empty model response")
            if attempt > 1:
                logger.info(
                    "Groq request succeeded on attempt %s/%s (key %s/%s, after retries)",
                    attempt, retries, (key_idx % len(keys)) + 1, len(keys),
                )
            return content
        except LLMError:
            last_error = LLMError(LLM_FALLBACK)
            # LLMError (empty response) — advance to next key
            key_idx += 1
        except Exception as exc:
            last_error = exc
            key_label = f"key {(key_idx % len(keys)) + 1}/{len(keys)}"
            if _is_rate_limit_error(exc):
                logger.warning(
                    "Groq rate limit on attempt %s/%s (%s), switching to next key: %s",
                    attempt, retries, key_label, type(exc).__name__,
                )
                # Immediately advance to next key for the next attempt
                key_idx += 1
            else:
                logger.warning(
                    "Groq request failed on attempt %s/%s (%s): %s",
                    attempt, retries, key_label, type(exc).__name__,
                )
                # Non-rate-limit error: also advance to next key so we
                # don't burn all retries on a single broken key
                key_idx += 1

    logger.error("Groq request failed after %s attempts across %s key(s)", retries, len(keys))
    raise LLMError(LLM_FALLBACK) from last_error


def complete_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 400,
    json_retries: int = 2,
) -> dict[str, Any]:
    """Call Groq in JSON mode and return a parsed dict.

    Retries the *entire* call (including complete()) up to ``json_retries``
    additional times when the LLM returns valid HTTP 200 but the content
    is not parseable JSON.  This covers the case where Groq returns
    truncated or wrapped text despite json_mode=True.
    """
    last_exc: Optional[Exception] = None
    for j_attempt in range(1 + json_retries):
        try:
            raw = complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise LLMError(LLM_FALLBACK)
            return parsed
        except json.JSONDecodeError as exc:
            last_exc = exc
            logger.warning(
                "Groq returned non-JSON content (attempt %s/%s), retrying",
                j_attempt + 1, 1 + json_retries,
            )
        except LLMError:
            raise
    raise LLMError(LLM_FALLBACK) from last_exc
