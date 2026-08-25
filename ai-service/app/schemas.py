from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OptionItem(BaseModel):
    option_id: str
    text: str
    doctor_id: Optional[UUID] = None


class MessageItem(BaseModel):
    role: str
    message: str
    timestamp: str


class ChatMessageRequest(BaseModel):
    patient_id: Optional[UUID] = None
    conversation_id: Optional[str] = None
    message: str
    language: Optional[str] = "english"

    @field_validator("message")
    @classmethod
    def message_must_be_present(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError("message is required and cannot be empty")
        return str(v).strip()

    @field_validator("language")
    @classmethod
    def default_language(cls, v: Optional[str]) -> str:
        if not v or not str(v).strip():
            return "english"
        return str(v).strip().lower()


class ChatMessageResponse(BaseModel):
    conversation_id: str
    patient_id: Optional[UUID] = None
    timestamp: str
    bot_message: str
    next_action: Optional[str] = None
    options: List[OptionItem] = Field(default_factory=list)
    conversation_history: List[MessageItem] = Field(default_factory=list)


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    patient_id: Optional[UUID] = None
    created_at: str
    updated_at: str
    messages: List[MessageItem]
    status: str = "ongoing"
    appointment_booked: Optional[UUID] = None
