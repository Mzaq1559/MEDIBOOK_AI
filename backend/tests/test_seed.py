import pytest
from app.services.seed import seed_database
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


def test_seed_database(db_session):
    result = seed_database(db_session)
    assert result["status"] in ("seeded", "already_seeded")

    # Verify seeded records exist
    clinic = db_session.query(Clinic).filter(Clinic.name == "Prime Care Clinic Taxila").first()
    assert clinic is not None
    assert clinic.city == "Taxila"

    doctors = db_session.query(Doctor).all()
    assert len(doctors) >= 3

    patients = db_session.query(Patient).all()
    assert len(patients) >= 3

    admin = db_session.query(User).filter(User.email == "admin@primecare.pk").first()
    assert admin is not None
    assert admin.user_type == "admin"
