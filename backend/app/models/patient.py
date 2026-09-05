import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date, Integer, Text, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)  # 'M', 'F', 'Other'
    blood_type = Column(String(5), nullable=True)
    allergies = Column(Text, nullable=True, default="[]")
    medical_conditions = Column(Text, nullable=True, default="[]")
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    emergency_contact_relation = Column(String(50), nullable=True)
    preferred_notification = Column(String(20), default="whatsapp", index=True)  # 'whatsapp', 'email', 'sms'
    total_appointments = Column(Integer, default=0)
    total_no_shows = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="patient")
