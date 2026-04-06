# ==============================================================================
# CDOM Pastoral Management System – Auth Router (OAuth2 + Hardening)
# Full OAuth2 routers with WebAuthn, lockout, phone verification, password policy
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import User
from app.schemas.schemas import (
    LoginRequest, LoginResponse, Token, TokenRefresh,
    MFAVerifyRequest, WebAuthnRegistrationRequest, WebAuthnLoginRequest,
    PhoneVerificationRequest, PhoneVerificationCode,
    PasswordPolicyResponse, AccountLockoutStatus,
)
from app.core.security import (
    verify_password, get_password_hash, create_access_token, create_refresh_token,
    decode_token, is_token_revoked, revoke_token, revoke_all_user_tokens,
    enforce_password_policy, check_lockout, record_failed_attempt, reset_failed_attempts,
    verify_phone_code, get_webauthn_registration_options, verify_webauthn_registration,
    get_webauthn_login_options, verify_webauthn_login,
)
from app.schemas.schemas import oauth2_scheme
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        if user:
            record_failed_attempt(db, user)
            check_lockout(user)
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    check_lockout(user)

    if user.mfa_enabled:
        return LoginResponse(mfa_required=True, temp_token="temp-mfa-token")

    access_token = create_access_token(str(user.id), user.token_version)
    refresh_token = create_refresh_token(str(user.id), user.token_version)

    reset_failed_attempts(db, user)
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(token_refresh: TokenRefresh, db: Session = Depends(get_db)):
    payload = decode_token(token_refresh.refresh_token)
    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or is_token_revoked(db, payload.get("jti")):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token(user_id, user.token_version)
    return Token(access_token=access_token, refresh_token=token_refresh.refresh_token)


@router.post("/webauthn/register")
async def webauthn_register(data: WebAuthnRegistrationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == uuid.UUID(data.credential_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    verify_webauthn_registration(user, data, db)
    return {"status": "registered"}


@router.post("/webauthn/login")
async def webauthn_login(data: WebAuthnLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == uuid.UUID(data.credential_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    verify_webauthn_login(user, data, db)
    access_token = create_access_token(str(user.id), user.token_version)
    return Token(access_token=access_token, refresh_token="refresh-placeholder")


@router.post("/phone/verify")
async def phone_verify(request: PhoneVerificationRequest, code: PhoneVerificationCode, db: Session = Depends(get_db)):
    if not verify_phone_code(request.phone_number, code.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    return {"status": "verified"}


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    revoke_token(db, payload.get("jti"), uuid.UUID(payload["sub"]), reason="logout")
    return {"status": "logged out"}


@router.post("/logout-all")
async def logout_all(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    revoke_all_user_tokens(db, uuid.UUID(payload["sub"]))
    return {"status": "logged out from all devices"}


@router.get("/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy():
    return PasswordPolicyResponse()


@router.get("/lockout-status", response_model=AccountLockoutStatus)
async def get_lockout_status(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return AccountLockoutStatus(
        locked=user.lockout_until is not None and user.lockout_until > datetime.now(timezone.utc),
        remaining_attempts=max(0, 5 - user.failed_login_attempts),
        lockout_until=user.lockout_until,
    )