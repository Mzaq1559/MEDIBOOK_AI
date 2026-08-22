from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class StandardErrorResponse(BaseModel):
    error: bool = True
    status_code: int
    message: str
    error_code: str
    timestamp: str
    request_id: str
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
