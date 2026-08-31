import re
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    user_type: str = Field(..., description="One of: patient, doctor, receptionist, admin")

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        valid_roles = {"patient", "doctor", "receptionist", "admin"}
        if v.lower() not in valid_roles:
            raise ValueError(f"user_type must be one of {valid_roles}")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Allow numbers, spaces, dashes, +
        cleaned = re.sub(r"[\s\-+()]", "", v)
        if not (10 <= len(cleaned) <= 15 and cleaned.isdigit()):
            raise ValueError("Phone number must contain between 10 and 15 digits")
        return v


class RegisterResponse(BaseModel):
    user_id: UUID
    email: str
    name: str
    user_type: str
    access_token: str
    refresh_token: str
    expires_in: int = 3600
    message: str = "Registration successful"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: UUID
    email: str
    name: str
    user_type: str
    access_token: str
    refresh_token: str
    expires_in: int = 3600
    patientId: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    expires_in: int = 3600


class LogoutRequest(BaseModel):
    token: Optional[str] = None


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class UserMeResponse(BaseModel):
    user_id: UUID
    email: str
    name: str
    user_type: str
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    # Role-specific profile IDs (patients.id / doctors.id) — different from users.id
    patient_id: Optional[UUID] = None
    doctor_id: Optional[UUID] = None
