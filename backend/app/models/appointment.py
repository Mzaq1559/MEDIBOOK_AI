import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(Uuid(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_time = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=30)
    status = Column(String(20), default="scheduled", nullable=False)  # 'scheduled', 'completed', 'no_show', 'cancelled', 'rescheduled'
    appointment_type = Column(String(20), default="in_person", nullable=False)  # 'in_person', 'video', 'phone'
    symptoms_reported = Column(Text, nullable=False)
    urgency_level = Column(String(20), nullable=False)  # 'low', 'normal', 'high', 'critical'
    urgency_reason = Column(String(100), nullable=True)  # machine-readable triage reason code
    notes = Column(Text, nullable=True)
    prescription_id = Column(Uuid(as_uuid=True), nullable=True)
    is_walk_in = Column(Boolean, default=False)
    reminder_sent_24h = Column(Boolean, default=False)
    reminder_sent_1h = Column(Boolean, default=False)
    feedback_score = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)
    google_calendar_event_id = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)

    # Relationships
    clinic = relationship("Clinic", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    prescription = relationship("Prescription", back_populates="appointment", uselist=False, foreign_keys="Prescription.appointment_id")

    __table_args__ = (
        Index("idx_appt_doc_time", "doctor_id", "appointment_time"),
        Index("idx_appt_clinic_time", "clinic_id", "appointment_time"),
        Index("idx_appt_pat_status", "patient_id", "status"),
    )
