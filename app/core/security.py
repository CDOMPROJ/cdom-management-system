from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# ==============================================================================
# 1. PASSWORD HASHING SETUP
# ==============================================================================
# We use bcrypt for enterprise-grade password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against the hashed version in the database."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password for secure database storage."""
    return pwd_context.hash(password)


# ==============================================================================
# 2. JWT TOKEN MANAGEMENT
# ==============================================================================
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a secure JSON Web Token (JWT).
    Used for both standard auth tokens and short-lived MFA temporary tokens.
    """
    to_encode = data.copy()

    # Set expiration
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration from settings (usually 120 minutes)
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Ensure the subject (sub) is a string, as required by JWT standards
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])

    # Sign the token using the secret key from the .env file
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and verifies a JWT token. Returns the payload if valid, None if expired/tampered.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None