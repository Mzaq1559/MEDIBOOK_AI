import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Callable
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database import get_db
from app.models.user import User

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    user_type: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "email": email,
        "user_type": user_type,
        "token_type": "access",
        "iss": settings.JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    email: str,
    user_type: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "email": email,
        "user_type": user_type,
        "token_type": "refresh",
        "iss": settings.JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iss", "sub"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Token has expired", "error_code": "EXPIRED_TOKEN"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid token", "error_code": "UNAUTHORIZED"}
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to retrieve the authenticated user from Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Missing or invalid authorization header", "error_code": "UNAUTHORIZED"}
        )

    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid token type for authorization", "error_code": "UNAUTHORIZED"}
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid token subject", "error_code": "UNAUTHORIZED"}
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Malformed user ID in token", "error_code": "UNAUTHORIZED"}
        )

    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "User not found or deleted", "error_code": "USER_NOT_FOUND"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "User account is inactive", "error_code": "FORBIDDEN"}
        )

    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Dependency to optionally retrieve the user if a valid token is provided."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("token_type") != "access":
            return None
        user_id = uuid.UUID(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        return user if user and user.is_active else None
    except Exception:
        return None


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory ensuring current user has one of the required roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.user_type not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": f"Access forbidden. Required role: {', '.join(allowed_roles)}",
                    "error_code": "FORBIDDEN"
                }
            )
        return current_user

    return role_checker
