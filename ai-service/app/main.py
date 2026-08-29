import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.chatbot import get_session, handle_message
from app.config import settings
from app.groq_client import LLMError, LLM_FALLBACK
from app.rag.config import rag_settings
from app.rag.embeddings import embedding_status
from app.rag.metrics import metrics as rag_metrics
from app.rag.vector_db import health_status as rag_vector_health
from app.schemas import ChatHistoryResponse, ChatMessageRequest, ChatMessageResponse

logger = logging.getLogger("medibook.ai.main")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MediBook AI Service",
    description="Virtual receptionist microservice: chat, symptom routing, and appointment booking via the clinic backend.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": True,
            "status_code": 429,
            "message": "Too many requests",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": f"req-{datetime.utcnow().timestamp()}",
            "details": {},
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": True,
            "status_code": 400,
            "message": "Invalid message format",
            "error_code": "INVALID_INPUT",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": f"req-{datetime.utcnow().timestamp()}",
            "details": {},
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        message = str(exc.detail.get("message") or "Request failed")
        error_code = str(exc.detail.get("error_code") or "ERROR")
    else:
        message = str(exc.detail)
        error_code = "ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": message,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": f"req-{datetime.utcnow().timestamp()}",
            "details": {},
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_rag_index() -> None:
    if not rag_settings.RAG_ENABLED or not rag_settings.RAG_AUTO_LOAD_ON_STARTUP:
        return
    try:
        from app.rag.knowledge_loader import ensure_knowledge_indexed

        ensure_knowledge_indexed()
    except Exception as exc:
        logger.warning("RAG knowledge auto-load failed (service will use fallback): %s", exc)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "medibook-ai-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/", tags=["Root"])
def root_index():
    return {
        "name": "MediBook AI Service",
        "docs": "/docs",
        "chat": "POST /api/chat/message",
        "history": "GET /api/chat/history/{conversation_id}",
        "rag_health": "GET /api/rag/health",
    }


@app.get("/api/rag/health", tags=["RAG"])
def rag_health_check():
    vector = rag_vector_health()
    return {
        "enabled": rag_settings.RAG_ENABLED,
        "vector_db": vector.get("vector_db", "unknown"),
        "embedding_model": embedding_status(),
        "collection": vector.get("collection", rag_settings.RAG_COLLECTION_NAME),
        "document_count": int(vector.get("document_count", "0")),
        "metrics": rag_metrics.snapshot(),
    }


@app.post(
    "/api/chat/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    tags=["Chat"],
)
@limiter.limit("60/minute")
def send_chat_message(
    request: Request,
    payload: ChatMessageRequest,
    authorization: Optional[str] = Header(default=None),
):
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid message format",
                "error_code": "INVALID_INPUT",
            },
        )
    
    conversation_id = payload.conversation_id or str(uuid4())

    try:
        result = handle_message(
            conversation_id=conversation_id,
            patient_id=str(payload.patient_id) if payload.patient_id else None,
            message=payload.message,
            language=payload.language or "english",
            authorization=authorization,
        )
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": LLM_FALLBACK,
                "error_code": "INTERNAL_ERROR",
            },
        )
    except Exception as exc:
        logger.error("Unexpected error in send_chat_message: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid or expired conversation_id",
                "error_code": "INVALID_CONVERSATION",
            },
        )

    patient_uuid = None
    if result.get("patient_id"):
        try:
            patient_uuid = UUID(str(result["patient_id"]))
        except (ValueError, TypeError):
            patient_uuid = payload.patient_id

    return ChatMessageResponse(
        conversation_id=result["conversation_id"],
        patient_id=patient_uuid,
        timestamp=result["timestamp"],
        bot_message=result["bot_message"],
        next_action=result["next_action"],
        options=result["options"],
        ui_data=result.get("ui_data"),
        conversation_history=result["conversation_history"],
    )


@app.get(
    "/api/chat/history/{conversation_id}",
    response_model=ChatHistoryResponse,
    tags=["Chat"],
)
def get_chat_history(conversation_id: str):
    session = get_session(conversation_id)
    now = datetime.utcnow().isoformat() + "Z"
    if not session:
        return ChatHistoryResponse(
            conversation_id=conversation_id,
            patient_id=None,
            created_at=now,
            updated_at=now,
            messages=[],
            status="not_found",
            appointment_booked=None,
        )
    booked = None
    if session.get("appointment_booked"):
        try:
            booked = UUID(str(session["appointment_booked"]))
        except (ValueError, TypeError):
            booked = None
    patient_uuid = None
    if session.get("patient_id"):
        try:
            patient_uuid = UUID(str(session["patient_id"]))
        except (ValueError, TypeError):
            patient_uuid = None
    return ChatHistoryResponse(
        conversation_id=conversation_id,
        patient_id=patient_uuid,
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=session["messages"],
        status=session.get("status") or "ongoing",
        appointment_booked=booked,
    )


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.AI_SERVICE_HOST,
        port=settings.AI_SERVICE_PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
