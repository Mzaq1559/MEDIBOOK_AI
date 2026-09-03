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
    "PLEASE CALL: 1122 (Emergency Rescue) or 15 (Ambulance)\n"
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
SPECIALTY_GENERAL_MEDICINE = "General Medicine"

# Chest discomfort keywords (English & Roman Urdu)
_CHEST_PATTERN = re.compile(
    r"\b(chest\s+pain|chest\s+tightness|chest\s+pressure|chest\s+heaviness|chest\s+burning|"
    r"pain\s+in\s+(?:my\s+)?chest|pain\s+in\s+(?:the\s+)?chest|"
    r"seene\s+me(?:in)?\s+dard|seene\s+me(?:in)?\s+jalan|seene\s+me(?:in)?\s+dabao|"
    r"dil\s+me(?:in)?\s+dard|chhati\s+(?:me(?:in)?|ka)\s+dard|"
    r"seene\s+ka\s+dard)\b",
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

# Heart-attack warning signs: chest pain spreading to another body area.
_CHEST_RADIATION_PATTERN = re.compile(
    r"(?:radiat(?:e|ing|es|ed)|spread(?:ing|s)?|moving|go(?:ing)?|travel(?:ing|ling)|"
    r"shoot(?:ing|s)?|extend(?:ing|s)?)\s+(?:to|into|toward|towards)\s+"
    r"(?:my\s+|the\s+)?(?:left|right|both)?\s*(?:arm|arms|jaw|neck|back|shoulder|shoulders)|"
    r"(?:left|right|both)\s+(?:arm|arms)\s+(?:pain|ache|dard|mein|may|tak)|"
    r"(?:baazu|bazoo|kandha|gardan|jabray|jabre|peeth)\s*(?:mein|me|tak)?\s+"
    r"(?:ja\s+raha|ja\s+rahi|phail|phel|dard|takleef)|"
    r"(?:seene|seena|chhati)\s+(?:ka|mein|me)\s+(?:dard\s+)?"
    r"(?:baazu|bazoo|kandha|gardan|jabray|jabre|peeth)\s+(?:mein|me|tak)",
    re.IGNORECASE,
)

# Worsening chest pain is itself a high-risk escalation, including follow-up answers.
_CHEST_WORSENING_PATTERN = re.compile(
    r"(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest|"
    r"seene\s+me(?:in)?\s+dard|dil\s+me(?:in)?\s+dard|chhati\s+me(?:in)?\s+dard)"
    r".{0,60}(?:getting\s+worse|worsening|increasing|increased|worse|"
    r"barh(?:ta|ti| raha| rahi)|zyada\s+kharab|bohot\s+bura|badh(?:ta|ti| raha| rahi))",
    re.IGNORECASE,
)

_WORSENING_FOLLOWUP_PATTERN = re.compile(
    r"(?:getting\s+worse|worsening|increasing|increased|very\s+worse|"
    r"much\s+worse|barh(?:ta|ti| raha| rahi)|zyada\s+kharab|bohot\s+bura|"
    r"badh(?:ta|ti| raha| rahi))",
    re.IGNORECASE,
)

_SEVERE_ASTHMA_PATTERN = re.compile(
    r"\b(?:severe|bad|acute)\s+asthma\b|\basthma\b.{0,40}\b(?:can't|cannot|unable|hard|difficulty)\s+breathe\b|"
    r"\b(?:dam|saans)\s+ghut(?:\s+(?:na|raha|rahi))?\b",
    re.IGNORECASE,
)
_CHILD_FEVER_PATTERN = re.compile(
    r"\b(?:baby|infant|newborn|toddler|child|kid|bacha|bachay|bachi)\b.{0,50}\b(?:high|very\s+high|tez|bohot\s+zyada)\s+fever\b|"
    r"\b(?:baby|infant|newborn|toddler|child|kid|bacha|bachay|bachi)\b.{0,50}\btez\s+bukhar\b",
    re.IGNORECASE,
)
_PREGNANCY_EMERGENCY_PATTERN = re.compile(
    r"\b(?:pregnan(?:t|cy)|expecting)\b.{0,60}\b(?:heavy\s+bleeding|severe\s+pain|abdominal\s+pain|water\s+broke|fainted|unconscious)\b|"
    r"\bhamla\s+hai\b.{0,60}\b(?:khoon|shadeed\s+dard|pet\s+mein\s+dard|behosh|pani)\b",
    re.IGNORECASE,
)

# Trauma, injury, allergic, abdominal, meningitis, and diabetic emergencies.
_BLEEDING_PATTERN = re.compile(
    r"\bbleed(?:ing|s)?\b|\bbleeding\s+(?:won't|will\s+not|doesn't|does\s+not)\s+stop\b|"
    r"khoon\s+(?:beh|nikal|ruk\s+nahi)|khoon\s+behta",
    re.IGNORECASE,
)
_FRACTURE_PATTERN = re.compile(
    r"\b(?:broken|fracture[d]?|bone\s+sticking\s+out|can't\s+move\s+(?:it|my\s+\w+)|cannot\s+move\s+(?:it|my\s+\w+))\b|"
    r"\b(?:haddi|hadi)\s+(?:toot|tut|bahar)\b|\b(?:haath|pair|taang|baazu)\s+nahi\s+hila",
    re.IGNORECASE,
)
_FALL_INJURY_PATTERN = re.compile(
    r"\b(?:fell|fall|fallen)\b.{0,50}\b(?:broke|broken|fracture|hurt|injur|cut|bleed)\w*\b|"
    r"\b(?:gir|giri|gira)\b.{0,50}\b(?:toot|tut|zakhm|chot|khoon)\w*\b",
    re.IGNORECASE,
)
_BURN_PATTERN = re.compile(
    r"\b(?:severe|deep|serious|bad|third[- ]degree|second[- ]degree)\s+burns?\b|"
    r"\b(?:burns?|jal(?:an| gaya| gayi))\b.{0,30}\b(?:severe|deep|serious|bad|bohot|shadeed)\b|"
    r"\b(?:bohot|shadeed|gehri?)\s+(?:jal|jalan)\b",
    re.IGNORECASE,
)
_DEEP_CUT_PATTERN = re.compile(
    r"\b(?:deep|large|serious|gaping|severe)\s+(?:cut|wound|laceration)\b|"
    r"\b(?:cut|wound|laceration)\b.{0,40}\b(?:deep|large|gaping|won't\s+stop|bleeding)\b|"
    r"\b(?:gehra|gehri|bara|bari)\s+(?:zakhm|kat|cut)\b",
    re.IGNORECASE,
)
_HEAD_INJURY_PATTERN = re.compile(
    r"\b(?:head injury|hit my head|hit to the head|head trauma|head\s+\w*\s*injur)\b|"
    r"\b(?:sar|sarr)\s+(?:par|pe)\s+(?:chot|lag|zarb)\b",
    re.IGNORECASE,
)
_HEAD_RED_FLAG_PATTERN = re.compile(
    r"\b(?:confusion|confused|disoriented|vomiting|vomit|passed\s+out|unconscious|fainted|fainting)\b|"
    r"\b(?:uljhan|behosh|ulti|qay|gash)\b",
    re.IGNORECASE,
)
_ANAPHYLAXIS_EXPOSURE_PATTERN = re.compile(
    r"\b(?:allerg(?:y|ic)|allergen|after\s+(?:eating|taking|using|an?\s+\w+)|insect\s+sting|bee\s+sting|food)\b|"
    r"\b(?:allergy|ke\s+baad|khanay\s+ke\s+baad|dawai\s+ke\s+baad)\b",
    re.IGNORECASE,
)
_THROAT_SWELLING_PATTERN = re.compile(
    r"\b(?:throat|tongue|lips?|face)\s+(?:swelling|swollen|closing|tight)\b|"
    r"\b(?:gala|zaban|hont|chehra)\s+(?:sooj|suj|band|phool)\w*\b",
    re.IGNORECASE,
)
_SEVERE_ABDOMINAL_PATTERN = re.compile(
    r"\b(?:severe|intense|excruciating|unbearable|very\s+bad|worst)\s+(?:abdominal|stomach|belly)\s+pain\b|"
    r"\b(?:abdominal|stomach|belly)\s+pain\b.{0,40}\b(?:severe|intense|unbearable|worsening|getting\s+worse)\b|"
    r"\b(?:pet|pait)\s+(?:mein|me)\s+(?:shadeed|bohot\s+zyada|sakht|bardasht\s+se\s+bahar)\s+dard\b",
    re.IGNORECASE,
)
_MENINGITIS_PATTERN = re.compile(
    r"\b(?:stiff|rigid)\s+neck\b|\b(?:gardan)\s+(?:akri|akad|sakht)\b",
    re.IGNORECASE,
)
_FEVER_PATTERN = re.compile(r"\b(?:high|very\s+high)\s+fever\b|\btez\s+bukhar\b|\bbukhar\s+bohot\s+zyada\b", re.IGNORECASE)
_DIABETES_PATTERN = re.compile(r"\b(?:diabet(?:es|ic)|diabetic|sugar\s+patient|blood\s+sugar)\b|\b(?:diabetes|sugar)\s+ka\s+mareez\b", re.IGNORECASE)
_DIABETIC_RED_FLAG_PATTERN = re.compile(
    r"\b(?:confusion|confused|drowsy|unconscious|passed\s+out|fainted|vomiting|vomit|very\s+weak|shaking|sweating)\b|"
    r"\b(?:uljhan|behosh|ulti|kamzori|kapkapi|paseena)\b",
    re.IGNORECASE,
)

# Standalone high-urgency emergency phrases (English & Roman Urdu), grouped by
# category so the appended explanation can name the emergency that matched.
_STANDALONE_EMERGENCY_GROUPS: list[tuple[str, list[str]]] = [
    # 1. Severe / acute chest pain on its own
    ("severe_chest_pain", [
        r"(?:severe|intense|crushing|heavy|sharp|unbearable|excruciating)\s+(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)",
        r"(?:chest\s+pain|pain\s+in\s+(?:my\s+|the\s+)?chest)\s+(?:is\s+)?(?:severe|unbearable|intense|excruciating)",
        r"seene\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef|jalan|dabao)",
        r"(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+seene\s+(?:me|mein)\s+(?:dard|takleef)",
        r"dil\s+(?:me|mein)\s+(?:shadeed|bohot(?:\s+zyada)?|tez|sakht)\s+(?:dard|takleef)",
    ]),
    # 2. Critical breathing crisis on its own
    ("breathing_crisis", [
        r"(?:can'?t|cannot|unable\s+to|can\s+not)\s+breathe",
        r"(?:not|stopped)\s+breathing",
        r"gasping\s+for\s+air|suffocating|severe\s+shortness\s+of\s+breath|severe\s+difficulty\s+breathing",
        r"saans\s+lene\s+me(?:in)?\s+dushwari",
        r"saans\s+lene\s+me(?:in)?\s+takleef",
        r"saans\s+nahi\s+aa\s+rahi",
        r"saans\s+ruk\s+gayi",
        r"saans\s+band",
        r"dam\s+ghut(?:\s+raha)?",
    ]),
    # 3. Unconsciousness / Fainting / Altered mental state
    ("unconsciousness", [
        r"\bunconscious\b|\bunresponsive\b|\bpassed\s+out\b|\bfainted\b|\bfainting\b|\bblacked\s+out\b|\bcollapse[d]?\b|\bloss\s+of\s+consciousness\b|\bnot\s+waking\s+up\b",
        r"\bbehosh\b|hosh\s+nahi|hosh\s+kho\s+(?:diya|baitha)|gash\s+aa\s+gaya",
    ]),
    # 4. Severe / Hemorrhagic Bleeding
    ("severe_bleeding", [
        r"(?:heavy|severe|profuse|excessive|non-stop|uncontrolled)\s+bleeding",
        r"bleeding\s+(?:heavily|severely|profusely|non-stop)",
        r"gushing\s+blood|coughing\s+(?:up\s+)?blood|vomiting\s+blood",
        r"bohot\s+(?:zyada\s+)?khoon|shadeed\s+khoon|khoon\s+ki\s+ulti|khoon\s+ruk\s+nahi|khoon\s+beh\s+raha",
    ]),
    # 5. Stroke / Neurological Emergency
    ("stroke", [
        r"\bstroke\b|\bmini-stroke\b|\btransient\s+ischemic\b|\bface\s+droop(?:ing)?\b|\bparalysis\b|\bslurred\s+speech\b|\bsudden\s+numbness\b",
        r"\bfalij\b|\blakwa\b|\bjism\s+sunn\b|\bchehra\s+terha\b",
    ]),
    # 6. Seizure / Convulsion
    ("seizure", [
        r"\bseizure[s]?\b|\bconvulsion[s]?\b|\bfits\b|\bepileptic\s+fit\b",
        r"\bmirgi\s+ka\s+daura\b|\bdaure\s+par\s+rahe\b|\bdaura\s+para\b|\bjhatke\s+lag\s+rahe\b",
    ]),
    # 7. Heart Attack / Cardiac Arrest
    ("heart_attack", [
        r"\bheart\s+attack\b|\bcardiac\s+arrest\b|\bheart\s+stopped\b",
        r"\bdil\s+ka\s+daura\b|\bdil\s+ka\s+attack\b|\bdil\s+band\b",
    ]),
    # 8. Poisoning / Overdose
    ("poisoning", [
        r"\boverdose\b|\bpoisoning\b|\bswallowed\s+poison\b|\btoxic\s+ingestion\b",
        r"\bzehar\b|\bzehrila\b|\bpoison\b",
    ]),
    # 9. Suicide / Self-Harm
    ("self_harm", [
        r"\bsuicid|\bkill\s+myself\b|\bend\s+my\s+life\b|\bhurt\s+myself\b",
        r"\bkhudkushi\b|\bjaan\s+dena\b",
    ]),
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
    r"\brashes?\b",
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
_GENERAL_MEDICINE = [
    r"\bheadache[s]?\b", r"\bmigraine[s]?\b", r"\bdizz(?:y|iness)\b", r"\bvertigo\b",
    r"\bback\s+pain\b", r"\blower\s+back\b", r"\bjoint\s+pain\b", r"\barthritis\b",
    r"\bstomach\s+(?:ache|pain)\b", r"\bbelly\s+(?:ache|pain)\b", r"\bnausea\b", r"\bdiarrhea\b",
    r"\bconstipation\b", r"\bfatigue\b", r"\btired(?:ness)?\b", r"\bsleep\s+(?:problem|issue|difficulty)s?\b",
    r"\binsomnia\b", r"\beye\s+(?:pain|problem|issue)s?\b", r"\bblurred\s+vision\b", r"\bvision\s+problem\b",
    r"\burinat(?:e|ion|ing)\s+(?:problem|pain|difficulty)\b", r"\bburning\s+(?:when|while)\s+urinating\b",
    r"\bperiod\s+(?:pain|problem)s?\b", r"\bmenstrual\s+(?:pain|problem)s?\b", r"\bfever\b",
    # Roman Urdu
    r"sar\s+(?:mein|me)\s+dard", r"aadha\s+sar\s+dard", r"chakkar", r"kamar\s+(?:mein|me)\s+dard",
    r"jodon\s+(?:mein|me)\s+dard", r"jodon\s+ka\s+dard", r"pet\s+(?:mein|me)\s+dard",
    r"matli", r"qabz", r"dast", r"thakan", r"neend\s+ka\s+masla", r"aankh(?:on)?\s+(?:mein|me)\s+dard",
    r"peshab\s+(?:mein|me)\s+(?:jalan|dard)", r"mahvari\s+ka\s+dard",
]


@dataclass
class TriageResult:
    is_emergency: bool
    specialty: Optional[str]
    urgency_level: str  # low | normal | high | critical
    reason: str


# One-sentence, plain-language explanations for each emergency category. They
# describe the pattern that was noticed (never a diagnosis) so the safety flag
# stays transparent. English only, matching the rest of the bot's output.
_EMERGENCY_EXPLANATIONS: dict[str, str] = {
    "chest_breathing": (
        "I flagged this because you mentioned chest pain together with trouble breathing, "
        "which can indicate a serious heart or lung emergency."
    ),
    "chest_radiation": (
        "I flagged this because you mentioned chest pain along with pain spreading to your "
        "arm, neck, jaw, or back, which can indicate a heart attack."
    ),
    "chest_worsening": (
        "I flagged this because you said your chest pain is getting worse, "
        "which can indicate a serious heart problem."
    ),
    "bleeding": (
        "I flagged this because you described active bleeding, which needs immediate attention."
    ),
    "fracture": (
        "I flagged this because you described a possible broken bone, which needs urgent medical care."
    ),
    "fall_injury": (
        "I flagged this because you described a fall that caused a serious injury, "
        "which needs urgent medical care."
    ),
    "burn": (
        "I flagged this because you described a serious burn, which needs immediate medical care."
    ),
    "deep_cut": (
        "I flagged this because you described a deep or severe cut, "
        "which can cause heavy bleeding and needs immediate attention."
    ),
    "head_injury": (
        "I flagged this because you mentioned a head injury along with confusion, vomiting, "
        "or passing out, which can indicate a serious injury."
    ),
    "anaphylaxis": (
        "I flagged this because your symptoms match signs of a severe allergic reaction."
    ),
    "severe_abdominal_pain": (
        "I flagged this because you described unbearable stomach pain, "
        "which can indicate a serious problem that needs immediate attention."
    ),
    "meningitis_signs": (
        "I flagged this because you mentioned a stiff neck along with a high fever, "
        "which can indicate a serious infection."
    ),
    "diabetic_emergency": (
        "I flagged this because you mentioned diabetes along with signs like confusion, "
        "heavy sweating, or passing out, which can indicate a dangerous blood sugar emergency."
    ),
    "severe_asthma": (
        "I flagged this because you described a severe asthma attack, "
        "which can quickly become life-threatening."
    ),
    "child_high_fever": (
        "I flagged this because you mentioned a baby or young child with a very high fever, "
        "which needs immediate medical attention."
    ),
    "pregnancy_emergency": (
        "I flagged this because you mentioned pregnancy along with heavy bleeding, "
        "severe pain, or fainting, which needs immediate attention."
    ),
    "severe_chest_pain": (
        "I flagged this because you described severe or crushing chest pain, "
        "which can indicate a heart attack."
    ),
    "breathing_crisis": (
        "I flagged this because you described being unable to breathe or a severe breathing "
        "crisis, which needs immediate attention."
    ),
    "unconsciousness": (
        "I flagged this because you mentioned being unconscious, fainting, or collapsing, "
        "which needs immediate attention."
    ),
    "severe_bleeding": (
        "I flagged this because you described severe bleeding, such as coughing up or "
        "vomiting blood, which needs immediate attention."
    ),
    "stroke": (
        "I flagged this because you mentioned signs of a stroke, such as face drooping, "
        "slurred speech, or sudden numbness, which need immediate attention."
    ),
    "seizure": (
        "I flagged this because you mentioned a seizure or fits, which needs immediate attention."
    ),
    "heart_attack": (
        "I flagged this because you mentioned a possible heart attack or cardiac arrest, "
        "which needs immediate emergency care."
    ),
    "poisoning": (
        "I flagged this because you mentioned poisoning or an overdose, "
        "which needs immediate emergency care."
    ),
    "self_harm": (
        "I flagged this because you mentioned harming yourself, "
        "and your safety right now is the most important thing."
    ),
}

_DEFAULT_EMERGENCY_EXPLANATION = (
    "I flagged this because your symptoms match a pattern that needs immediate medical attention."
)


def _emergency_category(text: str) -> Optional[str]:
    """Return the category key of the first emergency rule that matches text."""
    if not text or not text.strip():
        return None
    blob = text.lower()

    # Rule 1: Chest discomfort + ANY breathing distress
    if _CHEST_PATTERN.search(blob) and _BREATHING_PATTERN.search(blob):
        return "chest_breathing"

    # Rule 2: Chest pain radiating to arm, jaw, neck, back, or shoulder
    if _CHEST_PATTERN.search(blob) and _CHEST_RADIATION_PATTERN.search(blob):
        return "chest_radiation"

    # Rule 3: Worsening chest pain
    if _CHEST_WORSENING_PATTERN.search(blob):
        return "chest_worsening"
    if _CHEST_PATTERN.search(blob) and _WORSENING_FOLLOWUP_PATTERN.search(blob):
        return "chest_worsening"

    # Rule 4: Active bleeding, serious trauma, fractures, burns, deep wounds
    if _BLEEDING_PATTERN.search(blob):
        return "bleeding"
    if _FRACTURE_PATTERN.search(blob):
        return "fracture"
    if _FALL_INJURY_PATTERN.search(blob):
        return "fall_injury"
    if _BURN_PATTERN.search(blob):
        return "burn"
    if _DEEP_CUT_PATTERN.search(blob):
        return "deep_cut"

    # Rule 5: Head injury with red-flag symptoms
    if _HEAD_INJURY_PATTERN.search(blob) and _HEAD_RED_FLAG_PATTERN.search(blob):
        return "head_injury"

    # Rule 6: Anaphylaxis warning signs
    if _ANAPHYLAXIS_EXPOSURE_PATTERN.search(blob) and (
        _BREATHING_PATTERN.search(blob) or _THROAT_SWELLING_PATTERN.search(blob)
        or re.search(r"\bhives?\b|\burticaria\b|\bchhote\s+daane\b", blob, re.IGNORECASE)
    ):
        return "anaphylaxis"

    # Rule 7: Specific combined-condition emergencies — checked before the broader
    # standalone groups so that e.g. "asthma + dam ghut" fires severe_asthma rather
    # than the generic breathing_crisis wording.
    if _SEVERE_ASTHMA_PATTERN.search(blob):
        return "severe_asthma"
    if _CHILD_FEVER_PATTERN.search(blob):
        return "child_high_fever"
    if _PREGNANCY_EMERGENCY_PATTERN.search(blob):
        return "pregnancy_emergency"

    # Rule 8: Severe abdominal pain, meningitis signs, and diabetic crises.
    if _SEVERE_ABDOMINAL_PATTERN.search(blob):
        return "severe_abdominal_pain"
    if _MENINGITIS_PATTERN.search(blob) and _FEVER_PATTERN.search(blob):
        return "meningitis_signs"
    if _DIABETES_PATTERN.search(blob) and _DIABETIC_RED_FLAG_PATTERN.search(blob):
        return "diabetic_emergency"

    # Rule 9: Standalone acute emergency patterns
    for category, patterns in _STANDALONE_EMERGENCY_GROUPS:
        if any(re.search(p, blob, flags=re.IGNORECASE) for p in patterns):
            return category

    return None


def is_emergency(text: str) -> bool:
    return _emergency_category(text) is not None


# Backward-compatibility alias: existing callers that import _emergency_reason
# keep working without code changes.
_emergency_reason = _emergency_category


def emergency_explanation(text: str) -> str:
    """One plain-language sentence naming the pattern that triggered the alert."""
    category = _emergency_category(text)
    return _EMERGENCY_EXPLANATIONS.get(category or "", _DEFAULT_EMERGENCY_EXPLANATION)


def emergency_alert_with(explanation: Optional[str]) -> str:
    """Append the tailored explanation after the unchanged core emergency alert."""
    if not explanation:
        return EMERGENCY_ALERT
    return f"{EMERGENCY_ALERT}\n\n{explanation}"


def recommend_specialty(text: str) -> Optional[str]:
    if not text:
        return None
    blob = text.lower()
    scores = {
        SPECIALTY_CARDIOLOGY: sum(1 for p in _CARDIO if re.search(p, blob, re.IGNORECASE)),
        SPECIALTY_DERMATOLOGY: sum(1 for p in _DERM if re.search(p, blob, re.IGNORECASE)),
        SPECIALTY_ENT: sum(1 for p in _ENT if re.search(p, blob, re.IGNORECASE)),
        SPECIALTY_GENERAL_MEDICINE: sum(1 for p in _GENERAL_MEDICINE if re.search(p, blob, re.IGNORECASE)),
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
        return "high"
    if specialty == SPECIALTY_CARDIOLOGY:
        return "high"
    if specialty:
        return "normal"
    return "low"


def triage(text: str) -> TriageResult:
    emergency_code = _emergency_reason(text)
    if emergency_code:
        return TriageResult(
            is_emergency=True,
            specialty=None,
            urgency_level="critical",
            reason=emergency_code,
        )
    specialty = recommend_specialty(text)
    urgency = urgency_for(text, specialty, False)

    if specialty == SPECIALTY_CARDIOLOGY:
        reason = "cardiology_route"
    elif urgency == "high":
        reason = "high_urgency_marker"
    elif specialty:
        reason = "specialty_route"
    else:
        reason = "insufficient_detail"

    return TriageResult(
        is_emergency=False,
        specialty=specialty,
        urgency_level=urgency,
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
        "Which area is bothering you most ΓÇö ear, nose, or throat?",
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
