import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(Uuid(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True)
    doctor_id = Column(Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    medications = Column(Text, nullable=False, default="[]")  # JSON array
    instructions = Column(Text, nullable=True)
    validity_days = Column(Integer, default=30)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))

    # Relationships
    appointment = relationship("Appointment", back_populates="prescription", foreign_keys=[appointment_id])
    doctor = relationship("Doctor", back_populates="prescriptions")
    patient = relationship("Patient", back_populates="prescriptions")
