"""Prompt builder for grounded RAG triage."""

from __future__ import annotations

from typing import Any, Optional

from app.rag.models import RetrievedDocument

SYSTEM_INSTRUCTIONS = """You are MediBook AI, a clinic virtual receptionist in Pakistan.

You are NOT a doctor. You must NOT diagnose diseases. Do not invent medical facts.
Use ONLY the provided medical context for medical claims.
If retrieved context is insufficient, say there is insufficient information.
Never override deterministic emergency rules.
If symptoms suggest emergency care, set needs_emergency_care=true and urgency=emergency.

Your task:
- summarize the patient's reported symptoms
- identify appropriate medical specialty routing
- explain the recommendation conservatively
- identify when urgent evaluation may be appropriate
- avoid definitive diagnosis

Return JSON only with this schema:
{
  "urgency": "routine"|"soon"|"urgent"|"emergency",
  "specialty": "General Physician"|"Cardiologist"|"Dermatologist"|"ENT Specialist"|etc,
  "recommendation": "patient-facing guidance",
  "reasoning_summary": "brief internal-style summary",
  "red_flags": ["..."],
  "confidence": "low"|"medium"|"high",
  "needs_emergency_care": false,
  "sources": [{"id": "doc_id", "title": "display title", "type": "symptom|condition|..."}]
}

Only include sources that appear in RETRIEVED MEDICAL KNOWLEDGE."""


AVAILABLE_SPECIALTIES = [
    "General Physician",
    "Cardiologist",
    "Pulmonologist",
    "ENT Specialist",
    "Dermatologist",
    "Gastroenterologist",
    "Neurologist",
    "Orthopedist",
    "Urologist",
    "Gynecologist",
    "Ophthalmologist",
    "Dentist",
    "Pediatrician",
    "Psychiatrist",
]


class PromptAugmenter:
    def build_messages(
        self,
        patient_message: str,
        conversation_context: str,
        retrieved: list[RetrievedDocument],
        *,
        retrieval_status: str,
    ) -> list[dict[str, str]]:
        knowledge_block = self._format_knowledge(retrieved)
        user_content = (
            f"PATIENT MESSAGE:\n{patient_message}\n\n"
            f"CONVERSATION CONTEXT:\n{conversation_context or 'None'}\n\n"
            f"RETRIEVAL STATUS: {retrieval_status}\n\n"
            f"RETRIEVED MEDICAL KNOWLEDGE:\n{knowledge_block}\n\n"
            f"AVAILABLE SPECIALTIES:\n{', '.join(AVAILABLE_SPECIALTIES)}"
        )
        return [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_content},
        ]

    def build_correction_messages(
        self,
        original_messages: list[dict[str, str]],
        error_detail: str,
    ) -> list[dict[str, str]]:
        return original_messages + [
            {
                "role": "user",
                "content": (
                    "Your previous JSON was invalid. "
                    f"Error: {error_detail}. "
                    "Return valid JSON matching the required schema exactly."
                ),
            }
        ]

    def _format_knowledge(self, retrieved: list[RetrievedDocument]) -> str:
        if not retrieved:
            return "No relevant documents retrieved."
        blocks = []
        for doc in retrieved:
            blocks.append(
                f"- ID: {doc.id} | Type: {doc.doc_type} | Title: {doc.title} | "
                f"Relevance: {doc.score}\n  {doc.content}"
            )
        return "\n".join(blocks)
