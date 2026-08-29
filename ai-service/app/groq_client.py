"""Groq LLM client. Model ID comes only from GROQ_MODEL. Secrets are never logged."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from groq import Groq

from app.config import settings

logger = logging.getLogger("medibook.ai.groq")

LLM_FALLBACK = "Please try again or contact our team"


class LLMError(Exception):
    """Raised when the Groq API call fails after retries."""


def _client() -> Groq:
    key = (settings.GROQ_API_KEY or "").strip()
    if not key or key.startswith(("fake", "test", "dummy", "gsk_test", "mock")):
        raise LLMError(LLM_FALLBACK)
    return Groq(api_key=key)


def complete(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    json_mode: bool = False,
    retries: int = 3,
) -> str:
    """Call Groq chat completions. Returns assistant text. Never logs API keys."""
    last_error: Optional[Exception] = None
    create_kwargs: dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        create_kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(1, retries + 1):
        try:
            client = _client()
            response = client.chat.completions.create(**create_kwargs)
            choice = response.choices[0].message
            content = (choice.content or "").strip()
            if not content:
                raise LLMError("empty model response")
            return content
        except LLMError:
            last_error = LLMError(LLM_FALLBACK)
        except Exception as exc:
            last_error = exc
            logger.warning("Groq request failed on attempt %s/%s", attempt, retries)

    logger.error("Groq request failed after %s attempts", retries)
    raise LLMError(LLM_FALLBACK) from last_error


def complete_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    tool_choice: str = "auto",
    temperature: float = 0.2,
    max_tokens: int = 800,
    retries: int = 3,
) -> Any:
    """Call Groq chat completions with tool definitions. Returns choice message object."""
    last_error: Optional[Exception] = None
    create_kwargs: dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(1, retries + 1):
        try:
            client = _client()
            response = client.chat.completions.create(**create_kwargs)
            return response.choices[0].message
        except LLMError as exc:
            last_error = exc
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Groq request with tools failed on attempt %s/%s: %s", attempt, retries, exc)
            if "AuthenticationError" in type(exc).__name__ or "401" in str(exc):
                break

    logger.error("Groq request with tools failed after attempt(s)")
    raise LLMError(LLM_FALLBACK) from last_error




def complete_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 400,
) -> dict[str, Any]:
    raw = complete(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Groq returned non-JSON content")
        raise LLMError(LLM_FALLBACK) from exc
    if not isinstance(parsed, dict):
        raise LLMError(LLM_FALLBACK)
    return parsed
