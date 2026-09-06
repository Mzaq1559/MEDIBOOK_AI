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

# Chest discomfort keywords (English & Roman Urdu)
_CHEST_PATTERN = re.compile(
    r"\b(chest\s+pain|chest\s+tightness|chest\s+pressure|chest\s+heaviness|chest\s+burning|"
    r"pain\s+in\s+(?:my\s+)?chest|pain\s+in\s+(?:the\s+)?chest|"
    r"seene\s+me(?:in)?\s+dard|seene\s+me(?:in)?\s+jalan|seene\s+me(?:in)?\s+dabao|"
    r"dil\s+me(?:in)?\s+dard|chhati\s+me(?:in)?\s+dard)\b",
    re.IGNORECASE,
)

# Breathing distress / difficulty keywords (English & Roman Urdu)
_BREATHING_PATTERN = re.compile(
    r"\b(shortness\s+of\s+breath|short\s+of\s+breath|can'?t\s+breathe|cannot\s+breathe|"
    r"unable\s+to\s+breathe|can\s+not\s+breathe|not\s+breathing|stopped\s+breathing|"
    r"trouble\s+breathing|difficulty\s+breathing|hard\s+to\s+breathe|gasping(?:\s+for\s+air)?|"
    r"suffocating|choking|breathless(?:ness)?|"
    r"saans\s+lene\s+me(?:in)?\s+(?:dushwari|takleef|mushkil)|saans\s+nahi\s+aa\s+rahi|"
    r"saans\s+phool\s+rahi|saans\s+ruk|saans\s+band|dam\s+ghut)\b",
    re.IGNORECASE,
)

# Standalone high-urgency emergency phrases (English & Roman Urdu)
_STANDALONE_EMERGENCY_PATTERNS = [
    # 1. Severe / acute chest pain on its own
    r"(?:severe|intense|crushing|heavy|sharp|unbearable|excruciating)\s+(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)",
    r"(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)\s+(?:is\s+)?(?:severe|unbearable|intense|excruciating)",
    r"seene\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef|jalan|dabao)",
    r"(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+seene\s+(?:me|mein)\s+(?:dard|takleef)",
    r"dil\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef)",
    # 2. Critical breathing crisis on its own
    r"(?:can'?t|cannot|unable\s+to|can\s+not)\s+breathe",
    r"(?:not|stopped)\s+breathing",
    r"gasping\s+for\s+air|suffocating|severe\s+shortness\s+of\s+breath|severe\s+difficulty\s+breathing",
    r"saans\s+lene\s+me(?:in)?\s+dushwari",
    r"saans\s+lene\s+me(?:in)?\s+takleef",
    r"saans\s+nahi\s+aa\s+rahi",
    r"saans\s+ruk\s+gayi",
    r"saans\s+band",
    r"dam\s+ghut(?:\s+raha)?",
    # 3. Unconsciousness / Fainting / Altered mental state
    r"\bunconscious\b|\bunresponsive\b|\bpassed\s+out\b|\bfainted\b|\bfainting\b|\bblacked\s+out\b|\bcollapse[d]?\b|\bloss\s+of\s+consciousness\b|\bnot\s+waking\s+up\b",
    r"\bbehosh\b|hosh\s+nahi|hosh\s+kho\s+(?:diya|baitha)|gash\s+aa\s+gaya",
    # 4. Severe / Hemorrhagic Bleeding
    r"(?:heavy|severe|profuse|excessive|non-stop|uncontrolled)\s+bleeding",
    r"bleeding\s+(?:heavily|severely|profusely|non-stop)",
    r"gushing\s+blood|coughing\s+(?:up\s+)?blood|vomiting\s+blood",
    r"bohot\s+(?:zyada\s+)?khoon|shadeed\s+khoon|khoon\s+ki\s+ulti|khoon\s+ruk\s+nahi|khoon\s+beh\s+raha",
    # 5. Stroke / Neurological Emergency
    r"\bstroke\b|\bmini-stroke\b|\btransient\s+ischemic\b|\bface\s+droop(?:ing)?\b|\bparalysis\b|\bslurred\s+speech\b|\bsudden\s+numbness\b",
    r"\bfalij\b|\blakwa\b|\bjism\s+sunn\b|\bchehra\s+terha\b",
    # 6. Seizure / Convulsion
    r"\bseizure[s]?\b|\bconvulsion[s]?\b|\bfits\b|\bepileptic\s+fit\b",
    r"\bmirgi\s+ka\s+daura\b|\bdaure\s+par\s+rahe\b|\bdaura\s+para\b|\bjhatke\s+lag\s+rahe\b",
    # 7. Heart Attack / Cardiac Arrest
    r"\bheart\s+attack\b|\bcardiac\s+arrest\b|\bheart\s+stopped\b",
    r"\bdil\s+ka\s+daura\b|\bdil\s+ka\s+attack\b|\bdil\s+band\b",
    # 8. Poisoning / Overdose
    r"\boverdose\b|\bpoisoning\b|\bswallowed\s+poison\b|\btoxic\s+ingestion\b",
    r"\bzehar\b|\bzehrila\b|\bpoison\b",
    # 9. Suicide / Self-Harm
    r"\bsuicid|\bkill\s+myself\b|\bend\s+my\s+life\b|\bhurt\s+myself\b",
    r"\bkhudkushi\b|\bjaan\s+dena\b",
]

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
    # Roman Urdu
    r"seene\s+me(?:in)?\s+dard",
    r"dil\s+ki\s+dharkan",
    r"dil\s+me(?:in)?\s+dard",
    r"dil\s+ka\s+masla",
    r"dil\s+ki\s+takleef",
    r"blood\s+pressure",
    r"bp\s+high",
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
    # Roman Urdu
    r"kharish",
    r"khujli",
    r"daane",
    r"dane",
    r"jild",
    r"jild\s+ka\s+masla",
    r"chehre\s+par\s+daane",
    r"skin\s+allergy",
    r"surkhi",
    r"chhaley",
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
    # Roman Urdu
    r"gala\s+kharab",
    r"galay\s+me(?:in)?\s+dard",
    r"gala\s+paka",
    r"khansi",
    r"kaan\s+me(?:in)?\s+dard",
    r"naak\s+band",
    r"zukam",
    r"nazla",
    r"nazla\s+zukam",
    r"bukhar\s+aur\s+gala",
]


@dataclass
class TriageResult:
    is_emergency: bool
    specialty: Optional[str]
    urgency_level: str  # low | normal | high | critical
    reason: str


def _detect_emergency_reason(text: str) -> Optional[str]:
    """Return a machine-readable reason code if the text matches an emergency pattern, else None."""
    if not text or not text.strip():
        return None
    blob = text.lower()

    # Rule 1: Chest discomfort + ANY breathing distress
    if _CHEST_PATTERN.search(blob) and _BREATHING_PATTERN.search(blob):
        return "chest_pain_with_breathing_distress"

    # Rule 2: Standalone acute emergency patterns — check in priority order
    # Group 1: Severe chest pain
    _severe_chest = [
        r"(?:severe|intense|crushing|heavy|sharp|unbearable|excruciating)\s+(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)",
        r"(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)\s+(?:is\s+)?(?:severe|unbearable|intense|excruciating)",
        r"seene\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef|jalan|dabao)",
        r"(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+seene\s+(?:me|mein)\s+(?:dard|takleef)",
        r"dil\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef)",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _severe_chest):
        # Check for radiation patterns
        if re.search(r"radiat|spread|move|shift|arm|jaw|shoulder|back", blob, re.IGNORECASE):
            return "chest_pain_radiating"
        if re.search(r"worsen|increas|get\s+worse|getting\s+worse|progressive", blob, re.IGNORECASE):
            return "worsening_chest_pain"
        return "standalone_emergency_pattern"

    # Group 2: Critical breathing crisis
    _breathing_crisis = [
        r"(?:can'?t|cannot|unable\s+to|can\s+not)\s+breathe",
        r"(?:not|stopped)\s+breathing",
        r"gasping\s+for\s+air|suffocating|severe\s+shortness\s+of\s+breath|severe\s+difficulty\s+breathing",
        r"saans\s+lene\s+me(?:in)?\s+dushwari",
        r"saans\s+lene\s+me(?:in)?\s+takleef",
        r"saans\s+nahi\s+aa\s+rahi",
        r"saans\s+ruk\s+gayi",
        r"saans\s+band",
        r"dam\s+ghut(?:\s+raha)?",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _breathing_crisis):
        return "standalone_emergency_pattern"

    # Group 3: Unconsciousness / Fainting
    _unconscious = [
        r"\bunconscious\b|\bunresponsive\b|\bpassed\s+out\b|\bfainted\b|\bfainting\b|\bblacked\s+out\b|\bcollapse[d]?\b|\bloss\s+of\s+consciousness\b|\bnot\s+waking\s+up\b",
        r"\bbehosh\b|hosh\s+nahi|hosh\s+kho\s+(?:diya|baitha)|gash\s+aa\s+gaya",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _unconscious):
        return "standalone_emergency_pattern"

    # Group 4: Severe bleeding
    _bleeding = [
        r"(?:heavy|severe|profuse|excessive|non-stop|uncontrolled)\s+bleeding",
        r"bleeding\s+(?:heavily|severely|profusely|non-stop)",
        r"gushing\s+blood|coughing\s+(?:up\s+)?blood|vomiting\s+blood",
        r"bohot\s+(?:zyada\s+)?khoon|shadeed\s+khoon|khoon\s+ki\s+ulti|khoon\s+ruk\s+nahi|khoon\s+beh\s+raha",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _bleeding):
        return "severe_bleeding"

    # Group 5: Stroke / Neurological
    _stroke = [
        r"\bstroke\b|\bmini-stroke\b|\btransient\s+ischemic\b|\bface\s+droop(?:ing)?\b|\bparalysis\b|\bslurred\s+speech\b|\bsudden\s+numbness\b",
        r"\bfalij\b|\blakwa\b|\bjism\s+sunn\b|\bchehra\s+terha\b",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _stroke):
        return "standalone_emergency_pattern"

    # Group 6: Seizure / Convulsion
    _seizure = [
        r"\bseizure[s]?\b|\bconvulsion[s]?\b|\bfits\b|\bepileptic\s+fit\b",
        r"\bmirgi\s+ka\s+daura\b|\bdaure\s+par\s+rahe\b|\bdaura\s+para\b|\bjhatke\s+lag\s+rahe\b",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _seizure):
        return "standalone_emergency_pattern"

    # Group 7: Heart Attack / Cardiac Arrest
    _heart = [
        r"\bheart\s+attack\b|\bcardiac\s+arrest\b|\bheart\s+stopped\b",
        r"\bdil\s+ka\s+daura\b|\bdil\s+ka\s+attack\b|\bdil\s+band\b",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _heart):
        return "standalone_emergency_pattern"

    # Group 8: Poisoning / Overdose
    _poison = [
        r"\boverdose\b|\bpoisoning\b|\bswallowed\s+poison\b|\btoxic\s+ingestion\b",
        r"\bzehar\b|\bzehrila\b|\bpoison\b",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _poison):
        return "standalone_emergency_pattern"

    # Group 9: Suicide / Self-Harm
    _suicide = [
        r"\bsuicid\b|\bkill\s+myself\b|\bend\s+my\s+life\b|\bhurt\s+myself\b",
        r"\bkhudkushi\b|\bjaan\s+dena\b",
    ]
    if any(re.search(p, blob, flags=re.IGNORECASE) for p in _suicide):
        return "standalone_emergency_pattern"

    return None


def is_emergency(text: str) -> bool:
    return _detect_emergency_reason(text) is not None


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


def urgency_for(text: str, specialty: Optional[str], emergency: bool) -> tuple[str, str]:
    """Return (urgency_level, reason) tuple."""
    if emergency:
        return "critical", "standalone_emergency_pattern"
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
        "shadeed",
        "bohot zyada",
        "sakht",
        "khoon",
        "tez bukhar",
        "seene mein dard",
        "seene me dard",
        "saans me takleef",
    ]
    if any(m in blob for m in high_markers):
        return "high", "high_urgency_marker"
    if specialty == SPECIALTY_CARDIOLOGY:
        return "high", "cardiology_route"
    if specialty:
        return "normal", "specialty_route"
    return "low", "insufficient_detail"


def triage(text: str) -> TriageResult:
    emergency_reason = _detect_emergency_reason(text)
    if emergency_reason:
        return TriageResult(
            is_emergency=True,
            specialty=None,
            urgency_level="critical",
            reason=emergency_reason,
        )
    specialty = recommend_specialty(text)
    level, reason = urgency_for(text, specialty, False)
    return TriageResult(
        is_emergency=False,
        specialty=specialty,
        urgency_level=level,
        reason=reason,
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
