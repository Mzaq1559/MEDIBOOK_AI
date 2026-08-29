"""RAG safety layer — emergency rules always take priority over LLM/RAG."""

from __future__ import annotations

from app.symptom_triage import EMERGENCY_ALERT, is_emergency, triage as deterministic_triage
from app.rag.models import TriageLLMResponse, TriageResult, SourceReference

# Map display specialties to backend specialization filters
SPECIALTY_TO_BACKEND: dict[str, str] = {
    "General Physician": "General Medicine",
    "General Medicine": "General Medicine",
    "Cardiologist": "Cardiology",
    "Cardiology": "Cardiology",
    "Dermatologist": "Dermatology",
    "Dermatology": "Dermatology",
    "Pulmonologist": "Pulmonology",
    "ENT": "ENT",
    "ENT Specialist": "ENT",
    "Gastroenterologist": "Gastroenterology",
    "Neurologist": "Neurology",
    "Orthopedist": "Orthopedics",
    "Urologist": "Urology",
    "Gynecologist": "Gynecology",
    "Ophthalmologist": "Ophthalmology",
    "Dentist": "Dentistry",
    "Pediatrician": "Pediatrics",
    "Psychiatrist": "Psychiatry",
}

URGENCY_TO_LEVEL = {
    "routine": "normal",
    "soon": "normal",
    "urgent": "high",
    "emergency": "critical",
    "low": "low",
    "normal": "normal",
    "high": "high",
    "critical": "critical",
}


def check_emergency(text: str) -> bool:
    return is_emergency(text)


def emergency_result() -> TriageResult:
    return TriageResult(
        bot_message=EMERGENCY_ALERT,
        specialty=None,
        backend_specialization=None,
        urgency_level="critical",
        confidence="high",
        sources=[],
        rag_used=False,
        rag_status="success",
        fallback_used=False,
        needs_emergency_care=True,
    )


def map_specialty_to_backend(specialty: str | None) -> str | None:
    if not specialty:
        return None
    return SPECIALTY_TO_BACKEND.get(specialty, specialty)


def validate_llm_against_emergency(text: str, llm: TriageLLMResponse) -> TriageLLMResponse:
    """Never allow LLM to downgrade a confirmed emergency."""
    if is_emergency(text):
        llm.needs_emergency_care = True
        llm.urgency = "emergency"
        llm.specialty = llm.specialty or "Emergency"
        llm.recommendation = EMERGENCY_ALERT
    elif llm.needs_emergency_care and not is_emergency(text):
        # LLM flagged emergency — respect it conservatively
        llm.urgency = "emergency"
    return llm


def deterministic_fallback(text: str) -> TriageResult:
    result = deterministic_triage(text)
    specialty = result.specialty or "General Physician"
    backend_spec = map_specialty_to_backend(specialty)
    urgency = result.urgency_level

    if result.is_emergency:
        return emergency_result()

    if specialty and specialty != "General Physician":
        recommendation = (
            f"Based on your symptoms, I recommend seeing a {specialty}. "
            "This is general guidance only and not a medical diagnosis."
        )
    else:
        recommendation = (
            "A general physician can evaluate these symptoms. "
            "This is general guidance only and not a medical diagnosis."
        )

    return TriageResult(
        bot_message=recommendation,
        specialty=specialty,
        backend_specialization=backend_spec,
        urgency_level=urgency,
        confidence="medium",
        sources=[],
        rag_used=False,
        rag_status="insufficient_context",
        fallback_used=True,
        needs_emergency_care=False,
    )


def build_bot_message(llm: TriageLLMResponse, sources: list[SourceReference]) -> str:
    lines = [llm.recommendation.strip()]
    if llm.reasoning_summary:
        lines.append("")
        lines.append(llm.reasoning_summary.strip())
    lines.append("")
    lines.append(
        "⚠️ This information is for general guidance only and does not replace professional medical evaluation."
    )
    return "\n".join(lines)
