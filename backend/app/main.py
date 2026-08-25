from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.database import engine, Base
from app.middleware.security_headers import SecurityHeadersAndTracingMiddleware
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from app.middleware.error_handler import register_exception_handlers
from app.routes.auth import router as auth_router
from app.routes.doctors import router as doctors_router
from app.routes.patients import router as patients_router
from app.routes.clinics import router as clinics_router
from app.routes.appointments import router as appointments_router
from app.routes.analytics import router as analytics_router
from app.routes.chat import router as chat_router
from app.routes.users import router as users_router

# Initialize FastAPI Application
app = FastAPI(
    title="MediBook AI - Virtual Receptionist & Clinic Backend",
    description="Backend API for MediBook AI clinic management, real-time availability, appointment booking, and analytics.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Attach Slowapi Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Custom Global Exception Handlers
register_exception_handlers(app)

# Custom Security Headers & Request Tracing Middleware
app.add_middleware(SecurityHeadersAndTracingMiddleware)

# CORS Middleware
origins = settings.ALLOWED_ORIGINS
if isinstance(origins, str):
    origins = [o.strip() for o in origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(doctors_router)
app.include_router(patients_router)
app.include_router(clinics_router)
app.include_router(appointments_router)
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(users_router)


@app.get("/health", tags=["Health"], summary="Service Health Check")
def health_check():
    """Health check endpoint to verify backend operational readiness."""
    return {
        "status": "healthy",
        "service": "medibook-backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/", tags=["Root"], summary="Root API Index")
def root_index():
    """Root endpoint welcoming API consumers and linking to documentation."""
    return {
        "name": "MediBook AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
