import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey, Index, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    clinic_id = Column(Uuid(as_uuid=True), ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True, index=True)
    specialization = Column(String(100), nullable=True, index=True)
    qualifications = Column(Text, nullable=False, default='["MBBS"]')
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=2000.00)
    bio = Column(Text, nullable=True)
    is_available = Column(Boolean, default=True, index=True)
    max_patients_per_day = Column(Integer, default=20)
    appointment_duration_minutes = Column(Integer, default=30)
    languages_spoken = Column(Text, nullable=False, default='["Urdu", "English"]')
    rating = Column(Numeric(3, 2), default=0.0)
    total_appointments = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="doctor")
    clinic = relationship("Clinic", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="doctor")

    __table_args__ = (
        Index("idx_doctor_clinic_available", "clinic_id", "is_available"),
    )
