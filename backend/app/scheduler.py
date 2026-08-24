import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.appointment import Appointment
from app.services.calendar_service import sync_appointment
from app.services.email_service import send_reminder

logger = logging.getLogger(__name__)


async def start_scheduler():
    """
    Background scheduler loop running every 60 seconds to process:
    - 24-hour appointment email reminders
    - 1-hour appointment email reminders
    - Google Calendar synchronization for unsynced scheduled appointments
    """
    logger.info("INFO: Background scheduler started")
    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.utcnow()

                # 1. 24h Reminders window: appointment_time between NOW+23.9h and NOW+24.1h
                start_24h = now + timedelta(hours=23.9)
                end_24h = now + timedelta(hours=24.1)

                appts_24h = db.query(Appointment).filter(
                    Appointment.status == 'scheduled',
                    Appointment.reminder_sent_24h.is_(False),
                    Appointment.appointment_time >= start_24h,
                    Appointment.appointment_time <= end_24h
                ).all()

                # 2. 1h Reminders window: appointment_time between NOW+0.9h and NOW+1.1h
                start_1h = now + timedelta(hours=0.9)
                end_1h = now + timedelta(hours=1.1)

                appts_1h = db.query(Appointment).filter(
                    Appointment.status == 'scheduled',
                    Appointment.reminder_sent_1h.is_(False),
                    Appointment.appointment_time >= start_1h,
                    Appointment.appointment_time <= end_1h
                ).all()

                # 3. Unsynced Google Calendar appointments (created within last 7 days)
                seven_days_ago = now - timedelta(days=7)
                appts_cal = db.query(Appointment).filter(
                    Appointment.status == 'scheduled',
                    Appointment.google_calendar_event_id.is_(None),
                    Appointment.created_at >= seven_days_ago
                ).all()

                count_24h = 0
                for appt in appts_24h:
                    if send_reminder(appt.id, "24h", db):
                        count_24h += 1

                count_1h = 0
                for appt in appts_1h:
                    if send_reminder(appt.id, "1h", db):
                        count_1h += 1

                count_cal = 0
                for appt in appts_cal:
                    if sync_appointment(appt.id, db):
                        count_cal += 1

                logger.info(
                    f"[SCHEDULER] Sent {count_24h} 24h reminders, {count_1h} 1h reminders, synced {count_cal} to Calendar"
                )

            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("INFO: Background scheduler shutdown")
            break
        except Exception as e:
            logger.warning(f"[SCHEDULER] Error during background execution: {e}")

        await asyncio.sleep(60)
