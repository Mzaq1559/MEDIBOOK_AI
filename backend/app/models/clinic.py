import uuid
from datetime import datetime, time
from sqlalchemy import Column, String, Boolean, DateTime, Time, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    phone = Column(String(15), nullable=False)
    email = Column(String(255), nullable=False)
    working_hours_start = Column(Time, nullable=False, default=time(9, 0))
    working_hours_end = Column(Time, nullable=False, default=time(17, 0))
    working_days = Column(String(50), nullable=False, default="Mon,Tue,Wed,Thu,Fri")
    timezone = Column(String(50), default="Asia/Karachi")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    doctors = relationship("Doctor", back_populates="clinic", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="clinic")
    clinic_holidays = relationship("ClinicHoliday", back_populates="clinic", cascade="all, delete-orphan")
