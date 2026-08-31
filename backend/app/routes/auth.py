import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.core.security import get_password_hash, verify_password, validate_password_complexity
from app.core.auth import create_access_token, create_refresh_token, decode_token, get_current_user
from app.core.audit import log_audit_event
from app.middleware.rate_limiter import limiter
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, LogoutResponse,
    UserMeResponse
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Register a new user (patient, doctor, receptionist, or admin)."
)
@limiter.limit("5/minute")
def register_user(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    # 1. Validate password complexity
    if not validate_password_complexity(payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password must be at least 8 characters with 1 uppercase, 1 lowercase, 1 number, 1 special character",
                "error_code": "WEAK_PASSWORD"
            }
        )

    # 2. Check email uniqueness
    existing_user_email = db.query(User).filter(User.email == payload.email).first()
    if existing_user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Email already exists", "error_code": "EMAIL_DUPLICATE"}
        )

    # 3. Check phone uniqueness if provided
    if payload.phone:
        existing_user_phone = db.query(User).filter(User.phone == payload.phone).first()
        if existing_user_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Phone number already exists", "error_code": "PHONE_DUPLICATE"}
            )

    # 4. Hash password and create user
    hashed_pwd = get_password_hash(payload.password)
    new_user = User(
        id=uuid.uuid4(),
        email=payload.email,
        phone=payload.phone,
        name=payload.name,
        password_hash=hashed_pwd,
        user_type=payload.user_type,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.flush()

    # If registering as patient, automatically create default patient record
    if payload.user_type == "patient":
        patient_rec = Patient(
            id=uuid.uuid4(),
            user_id=new_user.id,
            date_of_birth=datetime(1990, 1, 1).date(),
            gender="M",
            emergency_contact_name="Emergency Contact",
            emergency_contact_phone=payload.phone or "03000000000",
            preferred_notification="whatsapp"
        )
        db.add(patient_rec)

    # Generate JWT tokens
    access_token = create_access_token(new_user.id, new_user.email, new_user.user_type)
    refresh_token = create_refresh_token(new_user.id, new_user.email, new_user.user_type)

    # Log audit event
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        action="registered_user",
        table_name="users",
        record_id=new_user.id,
        user_id=new_user.id,
        new_values={"email": new_user.email, "user_type": new_user.user_type, "name": new_user.name},
        ip_address=ip,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(new_user)

    return RegisterResponse(
        user_id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        user_type=new_user.user_type,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        message="Registration successful"
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate user with email and password, returning JWT access and refresh tokens."
)
@limiter.limit("10/minute")
def login_user(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "error_code": "INVALID_CREDENTIALS"}
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "error_code": "INVALID_CREDENTIALS"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "User account is disabled", "error_code": "FORBIDDEN"}
        )

    # Update last login timestamp
    user.last_login = datetime.utcnow()

    # Log audit event
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        action="login_user",
        table_name="users",
        record_id=user.id,
        user_id=user.id,
        ip_address=ip,
        user_agent=user_agent
    )

    db.commit()

    access_token = create_access_token(user.id, user.email, user.user_type)
    refresh_token = create_refresh_token(user.id, user.email, user.user_type)

    patient = None
    if user.user_type == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()

    return {
        "user_id": str(user.id),
        "patientId": str(patient.id) if user.user_type == "patient" and patient else None,
        "email": user.email,
        "name": user.name,
        "user_type": user.user_type,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 3600
    }


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Generate a new access token using a valid refresh token."
)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        token_data = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid or expired refresh token", "error_code": "INVALID_REFRESH_TOKEN"}
        )

    if token_data.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid token type for refresh", "error_code": "INVALID_REFRESH_TOKEN"}
        )

    user_id = uuid.UUID(token_data.get("sub"))
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "User not found or inactive", "error_code": "UNAUTHORIZED"}
        )

    new_access_token = create_access_token(user.id, user.email, user.user_type)
    return RefreshTokenResponse(
        access_token=new_access_token,
        expires_in=3600
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Invalidate session on client / server."
)
def logout_user(current_user: User = Depends(get_current_user)):
    return LogoutResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Retrieve profile details of the currently authenticated user."
)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Resolve role-specific profile IDs so callers always get the correct FK
    patient_id = None
    doctor_id = None
    if current_user.user_type == "patient":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if patient:
            patient_id = patient.id
    elif current_user.user_type == "doctor":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if doctor:
            doctor_id = doctor.id

    return UserMeResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        user_type=current_user.user_type,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        patient_id=patient_id,
        doctor_id=doctor_id,
    )
