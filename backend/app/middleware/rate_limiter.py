from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from starlette.responses import JSONResponse
from datetime import datetime

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Standardized handler for rate limit exceeded errors."""
    request_id = getattr(request.state, "request_id", "req-unknown")
    now_iso = datetime.utcnow().isoformat() + "Z"

    return JSONResponse(
        status_code=429,
        content={
            "error": True,
            "status_code": 429,
            "message": "Too many requests. Please try again later.",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "timestamp": now_iso,
            "request_id": request_id,
            "details": {"limit": str(exc.detail)}
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": "Rate limit exceeded"
        }
    )
