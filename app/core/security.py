# ==========================================
# CDOM Pastoral Management System – Core Security (SecurityPatch)
# JWT + Revocation using PostgreSQL + token_version + AuthMiddleware
# ==========================================

from datetime import datetime, timedelta, timezone
from typing import Optional, Callable
import uuid
from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.schemas.schemas import Token, TokenRefresh
from app.db.session import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, token_version: int, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "version": token_version
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
        "version": token_version
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def revoke_token(db: Session, jti: str, user_id: str, reason: str = "logout") -> None:
    revoked = RevokedToken(
        jti=jti,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        reason=reason
    )
    db.add(revoked)
    db.commit()


def is_token_revoked(db: Session, jti: str) -> bool:
    token = db.query(RevokedToken).filter(
        RevokedToken.jti == jti,
        RevokedToken.expires_at > datetime.now(timezone.utc)
    ).first()
    return token is not None


def revoke_all_user_tokens(db: Session, user_id: str) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.token_version += 1
        db.commit()


def cleanup_expired_revoked_tokens(db: Session) -> None:
    db.query(RevokedToken).filter(
        RevokedToken.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()


# ==========================================
# AUTH MIDDLEWARE (PROTECTS ALL PROTECTED ROUTES)
# ==========================================
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Skip auth for open routes
        if request.url.path in ["/auth/login", "/auth/refresh", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        authorization = request.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"}
            )

        token = authorization.split(" ")[1]

        try:
            payload = decode_token(token)
            jti = payload["jti"]
            user_id = payload["sub"]
            token_version = payload.get("version")

            # Get DB session
            db = next(get_db())

            # Check revocation
            if is_token_revoked(db, jti):
                return JSONResponse(status_code=401, content={"detail": "Token has been revoked"})

            # Check token version (logout-all-devices)
            user = db.query(User).filter(User.id == user_id).first()
            if not user or user.token_version != token_version:
                return JSONResponse(status_code=401, content={"detail": "Token invalid (logged out)"})

        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        # Token is valid → continue
        response = await call_next(request)
        return response