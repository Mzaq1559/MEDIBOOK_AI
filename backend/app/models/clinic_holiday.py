import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date, Text, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class ClinicHoliday(Base):
    __tablename__ = "clinic_holidays"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(Uuid(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    holiday_date = Column(Date, nullable=False)
    holiday_name = Column(String(255), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clinic = relationship("Clinic", back_populates="clinic_holidays")

    __table_args__ = (
        UniqueConstraint("clinic_id", "holiday_date", name="uq_clinic_holiday_date"),
    )
