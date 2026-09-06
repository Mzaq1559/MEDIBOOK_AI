# File: backend/app/utils/status.py

"""Utility constants and helper for appointment status values.

The application historically used a mix of snake_case and kebab-case strings for
appointment statuses (e.g. "no-show" vs "no_show").  For consistency we expose a
canonical set of snake_case constants and provide a simple normalisation
function that maps legacy values to the canonical form.  All write‑operations
should invoke :func:`normalize_status` before persisting to the database.
"""

from __future__ import annotations

# Canonical status values used throughout the code‑base and persisted in the DB.
STATUS_SCHEDULED = "scheduled"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_NO_SHOW = "no_show"

# Mapping of known legacy strings to the canonical values.
_LEGACY_STATUS_MAP = {
    "no-show": STATUS_NO_SHOW,
    "noShow": STATUS_NO_SHOW,
    "No-Show": STATUS_NO_SHOW,
    "NoShow": STATUS_NO_SHOW,
    "completed": STATUS_COMPLETED,
    "Completed": STATUS_COMPLETED,
    "cancelled": STATUS_CANCELLED,
    "Cancelled": STATUS_CANCELLED,
    "scheduled": STATUS_SCHEDULED,
    "Scheduled": STATUS_SCHEDULED,
}


def normalize_status(value: str | None) -> str | None:
    """Return the canonical snake_case status for *value*.

    If *value* is ``None`` the function returns ``None``.  Known legacy strings are
    mapped to their canonical equivalents; otherwise the original string is
    returned unchanged – this makes the function safe to call with values that
    are already correct.
    """
    if value is None:
        return None
    # Normalise whitespace and case for lookup.
    key = value.strip()
    # Direct lookup – handles already‑canonical values.
    if key in {STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW}:
        return key
    # Legacy mapping fallback.
    return _LEGACY_STATUS_MAP.get(key, key)
