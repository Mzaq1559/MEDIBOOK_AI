"""Pydantic models for RAG knowledge documents and triage responses."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

ConfidenceLevel = Literal["low", "medium", "high"]
UrgencyLevel = Literal["routine", "soon", "urgent", "emergency"]
RetrievalStatus = Literal["success", "insufficient_context", "error"]


class KnowledgeDocument(BaseModel):
    id: str
    type: str
    name: str = ""
    description: str = ""
    content: str = ""
    associated_conditions: list[str] = Field(default_factory=list)
    common_symptoms: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    recommended_specialties: list[str] = Field(default_factory=list)
    triage_level: str = "normal"
    trigger_patterns: list[str] = Field(default_factory=list)
    urgency: str = "routine"
    recommended_action: str = ""
    clinic_id: Optional[str] = None
    title: str = ""
    source: str = "internal_knowledge_base"
    version: str = "1.0"
    last_updated: str = "2026-08-28"

    @model_validator(mode="before")
    @classmethod
    def default_name_from_title(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("name"):
            data = dict(data)
            data["name"] = data.get("title") or data.get("id") or "Medical knowledge"
        return data

    def searchable_text(self) -> str:
        parts = [
            self.name,
            self.title,
            self.description,
            self.content,
            self.recommended_action,
            " ".join(self.associated_conditions),
            " ".join(self.common_symptoms),
            " ".join(self.red_flags),
            " ".join(self.recommended_specialties),
        ]
        return " ".join(p for p in parts if p).strip()

    def display_title(self) -> str:
        return self.title or self.name

    def to_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "doc_id": self.id,
            "type": self.type,
            "name": self.name,
            "specialty": self.recommended_specialties[0] if self.recommended_specialties else "",
            "urgency": self.urgency or self.triage_level,
            "clinic_id": self.clinic_id or "",
            "source": self.source,
            "version": self.version,
            "last_updated": self.last_updated,
        }
        return meta


class RetrievedDocument(BaseModel):
    id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def title(self) -> str:
        return str(self.metadata.get("name") or self.metadata.get("title") or self.id)

    @property
    def doc_type(self) -> str:
        return str(self.metadata.get("type") or "unknown")


class SourceReference(BaseModel):
    id: str
    title: str
    type: str = "symptom"


class TriageLLMResponse(BaseModel):
    urgency: UrgencyLevel = "routine"
    specialty: str = "General Physician"
    recommendation: str
    reasoning_summary: str = ""
    red_flags: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "medium"
    needs_emergency_care: bool = False
    sources: list[SourceReference] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> str:
        if isinstance(v, (int, float)):
            if v >= 0.75:
                return "high"
            if v >= 0.45:
                return "medium"
            return "low"
        val = str(v or "medium").lower().strip()
        if val in ("low", "medium", "high"):
            return val
        return "medium"


class TriageResult(BaseModel):
    bot_message: str
    specialty: Optional[str] = None
    backend_specialization: Optional[str] = None
    urgency_level: str = "normal"
    confidence: ConfidenceLevel = "medium"
    sources: list[SourceReference] = Field(default_factory=list)
    rag_used: bool = False
    rag_status: RetrievalStatus = "success"
    fallback_used: bool = False
    needs_emergency_care: bool = False
