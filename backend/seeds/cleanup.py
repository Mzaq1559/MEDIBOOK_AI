"""Delete stale and prior seed appointments so each startup is a clean slate.

Never touches users, patients, doctors, or clinics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.prescription import Prescription

# Same IDs as alembic/versions/002_seed_initial_data.py
PATIENT_1_ID = UUID("a3333333-3333-4333-a333-333333333333")
PATIENT_2_ID = UUID("a8888888-8888-4888-a888-888888888888")
PATIENT_3_ID = UUID("a9999999-9999-4999-a999-999999999999")

SEED_PATIENT_IDS = (PATIENT_1_ID, PATIENT_2_ID, PATIENT_3_ID)


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cleanup_appointments(session: Session) -> int:
    """Remove past appointments and all rows for known seed patients.

    Prescriptions that reference those appointments are deleted first.
    """
    now = utc_now_naive()
    to_remove = (
        session.query(Appointment.id)
        .filter(
            (Appointment.appointment_time < now)
            | (Appointment.patient_id.in_(SEED_PATIENT_IDS))
        )
        .all()
    )
    ids = [row[0] for row in to_remove]
    if not ids:
        return 0

    session.query(Prescription).filter(Prescription.appointment_id.in_(ids)).delete(
        synchronize_session=False
    )
    deleted = (
        session.query(Appointment)
        .filter(Appointment.id.in_(ids))
        .delete(synchronize_session=False)
    )
    session.flush()
    return int(deleted or 0)
