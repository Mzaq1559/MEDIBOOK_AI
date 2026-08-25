import uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from dateutil import parser as date_parser

from app.database import get_db
from app.models.user import User
from app.core.auth import require_roles
from app.services.analytics_service import get_dashboard_metrics, get_daily_summary
from app.schemas.analytics import DashboardResponse, DailySummaryResponse

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Clinic Operations Dashboard Metrics",
    description="Retrieve high-level operational statistics including appointment volume, doctor utilization, urgency breakdown, and symptom trends (Doctor or Admin only)."
)
def get_dashboard(
    clinic_id: Optional[uuid.UUID] = Query(None, description="Optional clinic UUID filter"),
    date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD), default is today"),
    current_user: User = Depends(require_roles("doctor", "admin", "receptionist")),
    db: Session = Depends(get_db)
):
    target_dt = None
    if date:
        try:
            target_dt = date_parser.parse(date).date()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid date format. Use YYYY-MM-DD.", "error_code": "INVALID_INPUT"}
            )

    return get_dashboard_metrics(
        db=db,
        clinic_id=clinic_id,
        target_date=target_dt
    )


@router.get(
    "/daily-summary",
    response_model=DailySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Comprehensive Daily Operations Summary",
    description="Retrieve status counts, patient flow breakdown, urgency metrics, and executive summary for a specific day."
)
def get_daily(
    date: str = Query(..., description="Target date (YYYY-MM-DD)"),
    doctor_id: Optional[uuid.UUID] = Query(None, description="Optional doctor UUID filter"),
    clinic_id: Optional[uuid.UUID] = Query(None, description="Optional clinic UUID filter"),
    current_user: User = Depends(require_roles("doctor", "admin", "receptionist")),
    db: Session = Depends(get_db)
):
    try:
        target_dt = date_parser.parse(date).date()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid date format. Use YYYY-MM-DD.", "error_code": "INVALID_INPUT"}
        )

    return get_daily_summary(
        db=db,
        target_date=target_dt,
        doctor_id=doctor_id,
        clinic_id=clinic_id
    )
