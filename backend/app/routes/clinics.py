import uuid
from datetime import datetime, time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.clinic_holiday import ClinicHoliday
from app.models.user import User
from app.core.auth import get_current_user, require_roles
from app.core.audit import log_audit_event
from app.schemas.clinic import (
    ClinicCreate, ClinicUpdate, ClinicListResponse, ClinicListItem,
    ClinicDetailResponse, ClinicDoctorItem, ClinicHolidayItem
)

router = APIRouter(prefix="/api/clinics", tags=["Clinics"])


@router.get(
    "",
    response_model=ClinicListResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Clinics",
    description="Retrieve a paginated list of all active registered clinics."
)
def list_clinics(
    city: Optional[str] = Query(None, description="Filter by city name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Clinic)
    if city:
        query = query.filter(Clinic.city.ilike(f"%{city}%"))
    if is_active is not None:
        query = query.filter(Clinic.is_active == is_active)

    total = query.count()
    clinics = query.offset(offset).limit(limit).all()

    items: List[ClinicListItem] = []
    for c in clinics:
        doc_count = db.query(Doctor).filter(Doctor.clinic_id == c.id).count()
        items.append(
            ClinicListItem(
                clinic_id=c.id,
                name=c.name,
                address=c.address,
                city=c.city,
                phone=c.phone,
                email=c.email,
                working_hours_start=c.working_hours_start.strftime("%H:%M") if c.working_hours_start else "09:00",
                working_hours_end=c.working_hours_end.strftime("%H:%M") if c.working_hours_end else "17:00",
                working_days=c.working_days,
                timezone=c.timezone or "Asia/Karachi",
                is_active=c.is_active,
                total_doctors=doc_count,
                total_appointments_this_month=0
            )
        )

    return ClinicListResponse(
        total=total,
        clinics=items
    )


@router.get(
    "/{clinic_id}",
    response_model=ClinicDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Clinic Details",
    description="Retrieve detailed clinic profile, associated doctors, and scheduled holidays."
)
def get_clinic_details(clinic_id: uuid.UUID, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Clinic not found", "error_code": "NOT_FOUND"}
        )

    doc_items: List[ClinicDoctorItem] = []
    for d in clinic.doctors:
        doc_items.append(
            ClinicDoctorItem(
                doctor_id=d.id,
                name=d.user.name if d.user else "Doctor",
                specialization=d.specialization,
                rating=float(d.rating or 0.0)
            )
        )

    hol_items: List[ClinicHolidayItem] = []
    for h in clinic.clinic_holidays:
        hol_items.append(
            ClinicHolidayItem(
                holiday_date=h.holiday_date.strftime("%Y-%m-%d"),
                holiday_name=h.holiday_name,
                reason=h.reason
            )
        )

    return ClinicDetailResponse(
        clinic_id=clinic.id,
        name=clinic.name,
        address=clinic.address,
        city=clinic.city,
        phone=clinic.phone,
        email=clinic.email,
        working_hours_start=clinic.working_hours_start.strftime("%H:%M") if clinic.working_hours_start else "09:00",
        working_hours_end=clinic.working_hours_end.strftime("%H:%M") if clinic.working_hours_end else "17:00",
        working_days=clinic.working_days,
        timezone=clinic.timezone or "Asia/Karachi",
        is_active=clinic.is_active,
        doctors=doc_items,
        holidays=hol_items
    )


@router.post(
    "",
    response_model=ClinicDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Clinic",
    description="Register a new clinic entity (Admin privilege required)."
)
def create_clinic(
    request: Request,
    payload: ClinicCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    # Check name duplicate
    existing = db.query(Clinic).filter(Clinic.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Clinic with this name already exists", "error_code": "CONFLICT"}
        )

    def parse_time_str(ts: str) -> time:
        parts = ts.split(":")
        return time(int(parts[0]), int(parts[1]))

    clinic = Clinic(
        id=uuid.uuid4(),
        name=payload.name,
        address=payload.address,
        city=payload.city,
        phone=payload.phone,
        email=payload.email,
        working_hours_start=parse_time_str(payload.working_hours_start),
        working_hours_end=parse_time_str(payload.working_hours_end),
        working_days=payload.working_days,
        timezone=payload.timezone,
        is_active=payload.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(clinic)

    log_audit_event(
        db=db,
        action="created_clinic",
        table_name="clinics",
        record_id=clinic.id,
        user_id=current_user.id,
        new_values={"name": clinic.name, "city": clinic.city},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(clinic)

    return ClinicDetailResponse(
        clinic_id=clinic.id,
        name=clinic.name,
        address=clinic.address,
        city=clinic.city,
        phone=clinic.phone,
        email=clinic.email,
        working_hours_start=clinic.working_hours_start.strftime("%H:%M"),
        working_hours_end=clinic.working_hours_end.strftime("%H:%M"),
        working_days=clinic.working_days,
        timezone=clinic.timezone,
        is_active=clinic.is_active,
        doctors=[],
        holidays=[]
    )


@router.put(
    "/{clinic_id}",
    response_model=ClinicDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Clinic Facility",
    description="Update clinic details, working hours, and operating days (Admin required)."
)
def update_clinic(
    request: Request,
    clinic_id: uuid.UUID,
    payload: ClinicUpdate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Clinic not found", "error_code": "NOT_FOUND"}
        )

    if payload.name is not None:
        clinic.name = payload.name
    if payload.address is not None:
        clinic.address = payload.address
    if payload.city is not None:
        clinic.city = payload.city
    if payload.phone is not None:
        clinic.phone = payload.phone
    if payload.email is not None:
        clinic.email = payload.email
    if payload.working_hours_start is not None:
        parts = payload.working_hours_start.split(":")
        clinic.working_hours_start = time(int(parts[0]), int(parts[1]))
    if payload.working_hours_end is not None:
        parts = payload.working_hours_end.split(":")
        clinic.working_hours_end = time(int(parts[0]), int(parts[1]))
    if payload.working_days is not None:
        clinic.working_days = payload.working_days
    if payload.timezone is not None:
        clinic.timezone = payload.timezone
    if payload.is_active is not None:
        clinic.is_active = payload.is_active

    clinic.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_clinic",
        table_name="clinics",
        record_id=clinic.id,
        user_id=current_user.id,
        new_values={"name": clinic.name, "city": clinic.city},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(clinic)

    return ClinicDetailResponse(
        clinic_id=clinic.id,
        name=clinic.name,
        address=clinic.address,
        city=clinic.city,
        phone=clinic.phone,
        email=clinic.email,
        working_hours_start=clinic.working_hours_start.strftime("%H:%M"),
        working_hours_end=clinic.working_hours_end.strftime("%H:%M"),
        working_days=clinic.working_days,
        timezone=clinic.timezone,
        is_active=clinic.is_active,
        doctors=[],
        holidays=[]
    )

