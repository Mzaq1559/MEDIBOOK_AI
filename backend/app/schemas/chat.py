from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field


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
