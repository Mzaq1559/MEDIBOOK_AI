"""NLU & Entity Extraction Helpers (Fast-path optimization helper)."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("medibook.ai.nlu")

MAX_HISTORY = 20


def is_confirm(text: str) -> bool:
    """Check if the text represents explicit confirmation."""
    return bool(re.search(r"\b(yes|yeah|yep|y|confirm|book it|go ahead|please book|haan|ji haan|theek hai|bilkul|kar do|sure|ok|okay)\b", text, re.I))


def is_decline(text: str) -> bool:
    """Check if the text represents explicit decline/cancellation of intent."""
    return bool(re.search(r"\b(no|nope|cancel|stop|nahi|na|mat karo|rehne do|chhor do|nevermind|don't)\b", text, re.I))


def is_off_topic_or_hostile(text: str) -> bool:
    """Check if message is hostile or off-topic gibberish."""
    b = text.lower().strip()
    return any(w in b for w in ("stupid", "idiot", "dumb", "shut up", "useless", "whatever", "u are stupid", "you are stupid", "fool", "nonsense"))


def extract_appointment_id(text: str) -> Optional[str]:
    """Extract an appointment UUID or ID string from text."""
    m = re.search(r"\b(?:APT-[\w-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    return m.group(0) if m else None


def extract_option_id(text: str) -> Optional[str]:
    """Extract a UUID or ISO-timestamp option_id from text."""
    m = re.search(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    if m:
        return m.group(1)
    iso = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
    if iso:
        return iso.group(1)
    return None
