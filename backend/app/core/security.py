import re
import bcrypt

PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>_~`\-+=[\]\\/]).{8,}$"
)


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash with 12 rounds."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def validate_password_complexity(password: str) -> bool:
    """Validate password against complexity rules."""
    if len(password) < 8:
        return False
    return bool(PASSWORD_REGEX.match(password))
