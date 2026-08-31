"""Insert a fresh set of future appointments after cleanup.

Safe to run on every backend start. Does not modify users or password hashes.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Appointment  # noqa: E402
from seeds.cleanup import cleanup_appointments  # noqa: E402

KARACHI = ZoneInfo("Asia/Karachi")

CLINIC_1_ID = UUID("11111111-1111-4111-a111-111111111111")
CLINIC_2_ID = UUID("22222222-2222-4222-a222-222222222222")
PATIENT_1_ID = UUID("a3333333-3333-4333-a333-333333333333")  # Ali Khan
PATIENT_2_ID = UUID("a8888888-8888-4888-a888-888888888888")  # Sara Ahmed
PATIENT_3_ID = UUID("a9999999-9999-4999-a999-999999999999")  # Usman Raza
DOCTOR_1_ID = UUID("b4444444-4444-4444-a444-444444444444")  # Ahmed Khan, clinic 1
DOCTOR_2_ID = UUID("b6666666-6666-4666-a666-666666666666")  # Fatima Zahra, clinic 1
DOCTOR_3_ID = UUID("b7777777-7777-4777-a777-777777777777")  # Tariq Mahmood, clinic 2

# (days_ahead, hour, minute, clinic, doctor, patient, symptoms, urgency)
APPOINTMENT_SPECS = [
    (1, 10, 0, CLINIC_1_ID, DOCTOR_1_ID, PATIENT_1_ID, "Chest tightness after climbing stairs", "normal"),
    (2, 14, 0, CLINIC_1_ID, DOCTOR_2_ID, PATIENT_1_ID, "Itchy rash on both forearms", "low"),
    (3, 11, 0, CLINIC_2_ID, DOCTOR_3_ID, PATIENT_1_ID, "Persistent dry cough for one week", "normal"),
    (4, 11, 30, CLINIC_1_ID, DOCTOR_1_ID, PATIENT_2_ID, "Palpitations during evening walks", "high"),
    (5, 9, 30, CLINIC_1_ID, DOCTOR_1_ID, PATIENT_1_ID, "Follow-up after recent ECG", "low"),
    (6, 10, 0, CLINIC_2_ID, DOCTOR_3_ID, PATIENT_3_ID, "Routine blood pressure review", "low"),
    (7, 15, 0, CLINIC_1_ID, DOCTOR_2_ID, PATIENT_1_ID, "Acne flare-up on the jawline", "low"),
    (8, 13, 0, CLINIC_1_ID, DOCTOR_2_ID, PATIENT_2_ID, "Patchy hair thinning on the scalp", "normal"),
    (10, 10, 0, CLINIC_1_ID, DOCTOR_1_ID, PATIENT_1_ID, "Mild fatigue and occasional dizziness", "normal"),
    (12, 16, 0, CLINIC_1_ID, DOCTOR_1_ID, PATIENT_3_ID, "Shortness of breath after light exercise", "high"),
]


def karachi_slot_to_utc_naive(days_ahead: int, hour: int, minute: int) -> datetime:
    now_k = datetime.now(KARACHI)
    local = (now_k + timedelta(days=days_ahead)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    if local <= now_k:
        local += timedelta(days=1)
    utc = local.astimezone(timezone.utc)
    return utc.replace(tzinfo=None)


def build_appointments(now_utc: datetime) -> list[Appointment]:
    rows: list[Appointment] = []
    for days, hour, minute, clinic_id, doctor_id, patient_id, symptoms, urgency in APPOINTMENT_SPECS:
        when = karachi_slot_to_utc_naive(days, hour, minute)
        if when <= now_utc:
            when = now_utc + timedelta(hours=2)
        rows.append(
            Appointment(
                id=uuid4(),
                clinic_id=clinic_id,
                doctor_id=doctor_id,
                patient_id=patient_id,
                appointment_time=when,
                duration_minutes=30,
                status="scheduled",
                appointment_type="in_person",
                symptoms_reported=symptoms,
                urgency_level=urgency,
            )
        )
    return rows


def seed() -> None:
    session = SessionLocal()
    try:
        deleted = cleanup_appointments(session)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = build_appointments(now_utc)
        session.add_all(rows)
        session.commit()
        print(
            f"[seed_appointments] deleted={deleted} inserted={len(rows)} "
            f"(all appointment_time > {now_utc.isoformat()}Z)"
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
