from app.routes.auth import router as auth_router
from app.routes.doctors import router as doctors_router
from app.routes.patients import router as patients_router
from app.routes.clinics import router as clinics_router
from app.routes.appointments import router as appointments_router
from app.routes.analytics import router as analytics_router
from app.routes.chat import router as chat_router
from app.routes.users import router as users_router

__all__ = [
    "auth_router",
    "doctors_router",
    "patients_router",
    "clinics_router",
    "appointments_router",
    "analytics_router",
    "chat_router",
    "users_router",
]
