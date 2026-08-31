"""Plain-text cleanup for patient-facing chatbot replies."""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_UNDERSCORE_BOLD_RE = re.compile(r"__(.+?)__", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def strip_markdown(text: str) -> str:
    """Remove common markdown markers so the chat UI can show plain text."""
    if not text:
        return text
    out = _BOLD_RE.sub(r"\1", text)
    out = _UNDERSCORE_BOLD_RE.sub(r"\1", out)
    out = _HEADING_RE.sub("", out)
    out = _INLINE_CODE_RE.sub(r"\1", out)
    out = out.replace("**", "").replace("__", "")
    return out.strip()


def lists_appointment_details(text: str) -> bool:
    """True when the reply already enumerates appointment fields in plain text."""
    if not text:
        return False
    cleaned = strip_markdown(text).lower()
    has_doctor = bool(re.search(r"\bdoctor\s*:", cleaned))
    has_when = bool(re.search(r"\b(date|time|date\s*&\s*time)\s*:", cleaned))
    has_clinic = bool(re.search(r"\bclinic\s*:", cleaned))
    has_reason = bool(re.search(r"\breason(\s+noted)?\s*:", cleaned))
    return has_doctor and (has_when or has_clinic or has_reason)
