import uuid
import logging
from datetime import datetime
from typing import Union
from fastapi import Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger("medibook.api")

HTTP_ERROR_CODE_MAP = {
    400: "INVALID_INPUT",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR"
}


def register_exception_handlers(app):
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:12]}")
        now_iso = datetime.utcnow().isoformat() + "Z"

        status_code = exc.status_code
        default_code = HTTP_ERROR_CODE_MAP.get(status_code, "ERROR")

        if isinstance(exc.detail, dict):
            message = exc.detail.get("message", "An error occurred")
            error_code = exc.detail.get("error_code", default_code)
            details = exc.detail.get("details", {})
        else:
            message = str(exc.detail)
            error_code = default_code
            details = {}

        return JSONResponse(
            status_code=status_code,
            content={
                "error": True,
                "status_code": status_code,
                "message": message,
                "error_code": error_code,
                "timestamp": now_iso,
                "request_id": request_id,
                "details": details
            },
            headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:12]}")
        now_iso = datetime.utcnow().isoformat() + "Z"

        error_details = []
        for error in exc.errors():
            loc = " -> ".join([str(l) for l in error.get("loc", [])])
            msg = error.get("msg", "")
            error_details.append({"location": loc, "message": msg})

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": 422,
                "message": "Input validation failed. Please check your request parameters.",
                "error_code": "INVALID_INPUT",
                "timestamp": now_iso,
                "request_id": request_id,
                "details": {"errors": error_details}
            }
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:12]}")
        now_iso = datetime.utcnow().isoformat() + "Z"

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": True,
                "status_code": 429,
                "message": "Rate limit exceeded. Please wait before making more requests.",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "timestamp": now_iso,
                "request_id": request_id,
                "details": {"limit": str(exc.detail)}
            }
        )

    @app.exception_handler(IntegrityError)
    async def db_integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:12]}")
        now_iso = datetime.utcnow().isoformat() + "Z"
        logger.error(f"[{request_id}] Database integrity error: {str(exc)}")

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": True,
                "status_code": 409,
                "message": "Database constraint violation or conflict.",
                "error_code": "CONFLICT",
                "timestamp": now_iso,
                "request_id": request_id,
                "details": {}
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req-{uuid.uuid4().hex[:12]}")
        now_iso = datetime.utcnow().isoformat() + "Z"
        logger.error(f"[{request_id}] Unhandled server exception: {str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": 500,
                "message": "Internal server error. Please try again later.",
                "error_code": "INTERNAL_ERROR",
                "timestamp": now_iso,
                "request_id": request_id,
                "details": {}
            }
        )
