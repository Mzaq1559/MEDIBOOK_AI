import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor import Doctor
from app.middleware.rate_limiter import limiter
from app.schemas.chat import (
    ChatMessageRequest, ChatMessageResponse,
    ChatHistoryResponse, OptionItem, MessageItem
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# In-memory session store for conversational history
_chat_sessions: Dict[str, List[MessageItem]] = {}


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send Message to Virtual Receptionist",
    description="Conversational intake for symptoms, specialist recommendation, and appointment booking."
)
@limiter.limit("60/minute")
def send_chat_message(
    request: Request,
    payload: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    conv_id = payload.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.utcnow().isoformat() + "Z"

    if conv_id not in _chat_sessions:
        _chat_sessions[conv_id] = []

    _chat_sessions[conv_id].append(
        MessageItem(
            role="user",
            message=payload.message,
            timestamp=now_iso
        )
    )

    # Basic triage / recommendation logic
    msg_lower = payload.message.lower()
    options: List[OptionItem] = []
    bot_message = "Hello! I am MediBook AI. How can I assist you with your health or appointment booking today?"
    next_action = "waiting_for_input"

    if any(em in msg_lower for em in ["severe chest pain", "cannot breathe", "unconscious", "heavy bleeding"]):
        bot_message = (
            "🚨 EMERGENCY ALERT 🚨\n"
            "This requires IMMEDIATE medical attention. Please call emergency services (1100 / 15) "
            "or proceed to the nearest emergency room immediately!"
        )
        next_action = "emergency_redirect"
    elif "appointment" in msg_lower or "book" in msg_lower or "doctor" in msg_lower:
        doctors = db.query(Doctor).filter(Doctor.is_available.is_(True)).limit(5).all()
        bot_message = "I would be happy to help you book an appointment! Here are our available doctors:"
        for d in doctors:
            doc_name = d.user.name if d.user else "Doctor"
            options.append(
                OptionItem(
                    option_id=f"doc-{d.id}",
                    text=f"{doc_name} ({d.specialization})",
                    doctor_id=d.id
                )
            )
        next_action = "waiting_for_doctor_selection"
    elif "hours" in msg_lower or "timing" in msg_lower:
        bot_message = (
            "Our clinic operating hours are Monday through Friday, 9:00 AM to 5:00 PM (Asia/Karachi timezone). "
            "We are closed on weekends and national holidays."
        )

    _chat_sessions[conv_id].append(
        MessageItem(
            role="assistant",
            message=bot_message,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    )

    return ChatMessageResponse(
        conversation_id=conv_id,
        patient_id=payload.patient_id,
        timestamp=now_iso,
        bot_message=bot_message,
        next_action=next_action,
        options=options,
        conversation_history=_chat_sessions[conv_id]
    )


@router.get(
    "/history/{conversation_id}",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation History",
    description="Retrieve chronological dialogue history for an active or completed chat session."
)
def get_chat_history(conversation_id: str):
    history = _chat_sessions.get(conversation_id, [])
    now_iso = datetime.utcnow().isoformat() + "Z"

    return ChatHistoryResponse(
        conversation_id=conversation_id,
        patient_id=None,
        created_at=history[0].timestamp if history else now_iso,
        updated_at=history[-1].timestamp if history else now_iso,
        messages=history,
        status="ongoing" if history else "not_found",
        appointment_booked=None
    )
