import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Date, Time, Integer, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    is_holiday = Column(Boolean, default=False)
    holiday_reason = Column(String(255), nullable=True)
    break_start = Column(Time, nullable=True)
    break_end = Column(Time, nullable=True)
    max_patients = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    doctor = relationship("Doctor", back_populates="schedules")

    __table_args__ = (
        UniqueConstraint("doctor_id", "date", name="uq_doctor_schedule_date"),
    )
