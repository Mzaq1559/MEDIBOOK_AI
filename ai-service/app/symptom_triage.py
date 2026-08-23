"""Symptom routing and emergency detection.

This module only routes to a specialist and flags urgency. It does not diagnose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

EMERGENCY_ALERT = (
    "🚨 EMERGENCY ALERT 🚨\n"
    "\n"
    "This requires IMMEDIATE medical attention. Do NOT wait.\n"
    "\n"
    "PLEASE CALL: 1100 (Emergency) or 15 (Ambulance)\n"
    "Or go to the nearest emergency room immediately!\n"
    "\n"
    "This is a medical emergency - our clinic appointment system is NOT suitable for this situation.\n"
    "\n"
    "Are you safe? Do you have someone who can help you?"
)

# Clinic specialties present in Person A's seed data.
SPECIALTY_CARDIOLOGY = "Cardiologist"
SPECIALTY_DERMATOLOGY = "Dermatologist"
SPECIALTY_ENT = "ENT Specialist"

_EMERGENCY_PHRASES = [
    r"cannot breathe",
    r"can't breathe",
    r"cant breathe",
    r"can not breathe",
    r"unable to breathe",
    r"not breathing",
    r"stopped breathing",
    r"unconscious",
    r"unresponsive",
    r"heavy bleeding",
    r"bleeding heavily",
    r"severe bleeding",
    r"stroke",
    r"seizure",
    r"heart attack",
    r"suicid",
    r"overdose",
]

_SEVERE_CHEST = re.compile(r"severe\s+chest\s+pain", re.IGNORECASE)
_CHEST_PAIN = re.compile(r"chest\s+pain", re.IGNORECASE)
_BREATHING_CRISIS = re.compile(
    r"(can'?t|cannot|unable to|can not)\s+breathe|not breathing|stopped breathing",
    re.IGNORECASE,
)

_CARDIO = [
    r"chest pain",
    r"shortness of breath",
    r"short of breath",
    r"palpitation",
    r"heart racing",
    r"irregular heartbeat",
    r"high blood pressure",
    r"hypertension",
    r"angina",
]
_DERM = [
    r"\brash\b",
    r"\bacne\b",
    r"\bitch",
    r"skin",
    r"eczema",
    r"psoriasis",
    r"hives",
    r"mole",
    r"hair loss",
]
_ENT = [
    r"\bear\b",
    r"\bsore throat\b",
    r"\bthroat\b",
    r"\bsinus",
    r"\bnose\b",
    r"\bnasal",
    r"\btinnitus",
    r"hearing",
    r"tonsil",
    r"\bcough\b",
    r"\bcold\b",
]


@dataclass
class TriageResult:
    is_emergency: bool
    specialty: Optional[str]
    urgency_level: str  # low | normal | high | critical
    reason: str


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def is_emergency(text: str) -> bool:
    if not text or not text.strip():
        return False
    blob = text.lower()

    if _SEVERE_CHEST.search(blob) and _BREATHING_CRISIS.search(blob):
        return True
    if _CHEST_PAIN.search(blob) and _BREATHING_CRISIS.search(blob) and "severe" in blob:
        return True
    if _has_any(blob, _EMERGENCY_PHRASES):
        # "heart attack" / "can't breathe" / unconscious etc. skip clinic booking
        return True
    return False


def recommend_specialty(text: str) -> Optional[str]:
    if not text:
        return None
    blob = text.lower()
    scores = {
        SPECIALTY_CARDIOLOGY: sum(1 for p in _CARDIO if re.search(p, blob, re.IGNORECASE)),
        SPECIALTY_DERMATOLOGY: sum(1 for p in _DERM if re.search(p, blob, re.IGNORECASE)),
        SPECIALTY_ENT: sum(1 for p in _ENT if re.search(p, blob, re.IGNORECASE)),
    }
    best = max(scores.values())
    if best <= 0:
        return None
    # Prefer cardiology on ties involving chest/breathing language.
    if scores[SPECIALTY_CARDIOLOGY] == best and best > 0:
        return SPECIALTY_CARDIOLOGY
    for spec, score in scores.items():
        if score == best:
            return spec
    return None


def urgency_for(text: str, specialty: Optional[str], emergency: bool) -> str:
    if emergency:
        return "critical"
    blob = (text or "").lower()
    high_markers = [
        "severe",
        "intense",
        "worsening",
        "can't sleep",
        "cannot sleep",
        "chest pain",
        "shortness of breath",
        "bleeding",
        "high fever",
    ]
    if any(m in blob for m in high_markers):
        return "high"
    if specialty == SPECIALTY_CARDIOLOGY:
        return "high"
    if specialty:
        return "normal"
    return "low"


def triage(text: str) -> TriageResult:
    emergency = is_emergency(text)
    if emergency:
        return TriageResult(
            is_emergency=True,
            specialty=None,
            urgency_level="critical",
            reason="emergency_pattern",
        )
    specialty = recommend_specialty(text)
    return TriageResult(
        is_emergency=False,
        specialty=specialty,
        urgency_level=urgency_for(text, specialty, False),
        reason="specialty_route" if specialty else "insufficient_detail",
    )


FOLLOW_UP_QUESTIONS = {
    SPECIALTY_CARDIOLOGY: [
        "When did this start?",
        "Have you experienced this before?",
        "Is the pain sharp, dull, or pressing?",
    ],
    SPECIALTY_DERMATOLOGY: [
        "How long have you had this skin concern?",
        "Is it itchy, painful, or spreading?",
        "Have you already tried any creams or medication for it?",
    ],
    SPECIALTY_ENT: [
        "Which area is bothering you most — ear, nose, or throat?",
        "Do you have fever, or is it mainly pain or congestion?",
        "How long have these symptoms lasted?",
    ],
    "default": [
        "When did this start?",
        "Have you had this before?",
        "Is it getting worse, staying the same, or improving?",
    ],
}


def follow_ups_for(specialty: Optional[str]) -> list[str]:
    return FOLLOW_UP_QUESTIONS.get(specialty or "default", FOLLOW_UP_QUESTIONS["default"])
