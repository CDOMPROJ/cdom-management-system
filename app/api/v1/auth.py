from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone
import pyotp
import uuid
import secrets

# PHASE 3 SECURE IMPORTS
from app.core.security import get_current_user, get_password_hash, verify_password, create_access_token, decode_access_token
from app.core.authorization import PermissionChecker, OwnershipService, generate_device_fingerprint
from app.db.session import get_db
from app.models.all_models import User, UserSession, ElevatedToken
from app.schemas.schemas import LoginRequest, LoginResponse, MFAVerifyRequest, SessionResponse, ElevatedTokenRequest

router = APIRouter()

ownership_service = OwnershipService()


# ==============================================================================
# 1. THE LOGIN ENDPOINT (MFA INTERCEPTOR) – ORIGINAL RICH LOGIC PRESERVED
# ==============================================================================
@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Standard login flow. If the user has MFA enabled, they are denied a full JWT
    and instead receive a Temporary Token to proceed to the TOTP verification step.
    """
    query = select(User).where(User.email == credentials.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact SysAdmin.")

    # MFA Check
    if user.mfa_enabled:
        temp_payload = {"sub": str(user.id), "mfa_pending": True}
        temp_token = create_access_token(data=temp_payload, expires_delta=5)  # 5 min expiry
        return {
            "mfa_required": True,
            "temp_token": temp_token,
            "message": "MFA token required to complete login."
        }

    # Standard Login (No MFA)
    jwt_payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(data=jwt_payload)

    return {"access_token": access_token, "mfa_required": False}


# ==============================================================================
# 2. MFA VERIFICATION ENDPOINT – ORIGINAL RICH LOGIC PRESERVED
# ==============================================================================
@router.post("/verify-mfa", response_model=LoginResponse)
async def verify_mfa(request: MFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Validates the 6-digit Authenticator code and issues the final JWT."""
    payload = decode_access_token(request.temp_token)
    if not payload or not payload.get("mfa_pending"):
        raise HTTPException(status_code=401, detail="Invalid or expired temporary token.")

    user_id = payload.get("sub")
    user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()

    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not configured for this user.")

    # Verify the TOTP Math
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(request.code):
        raise HTTPException(status_code=401, detail="Invalid authentication code.")

    # Issue Full Token
    jwt_payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    return {"access_token": create_access_token(data=jwt_payload), "mfa_required": False}


# ==============================================================================
# 3. SESSION TRACKING API (REPO PHASE 3.4) – FULLY PRESERVED
# ==============================================================================
class SessionResponse(BaseModel):
    id: str
    device_fingerprint: str
    ip_address: str
    user_agent: str
    last_active: datetime
    is_trusted: bool


@router.get("/sessions", response_model=List[SessionResponse])
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # PHASE 3 ABAC
    await PermissionChecker("user:read")(current_user)

    result = await db.execute(
        select(UserSession).where(UserSession.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/sessions/{session_id}/logout")
async def logout_specific_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # PHASE 3 ABAC
    await PermissionChecker("user:write")(current_user)

    session = await db.get(UserSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": "Session logged out successfully"}


# ==============================================================================
# 4. ELEVATED ACCESS TOKEN (BISHOP-ONLY) – REPO PHASE 3.4
# ==============================================================================
@router.post("/elevate")
async def create_elevated_token(
    request: ElevatedTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # PHASE 3 ABAC
    await PermissionChecker("bishop:elevate")(current_user)

    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can create elevated tokens")
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    elevated = ElevatedToken(
        token=token,
        user_id=current_user.id,
        expires_at=expires_at,
        reason=request.reason
    )
    db.add(elevated)
    await db.commit()
    return {"token": token, "expires_at": expires_at.isoformat()}


# ==============================================================================
# 5. TRUSTED DEVICE MANAGEMENT – REPO PHASE 3.4
# ==============================================================================
@router.post("/devices/trust")
async def trust_device(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # PHASE 3 ABAC
    await PermissionChecker("user:write")(current_user)

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    fingerprint = generate_device_fingerprint(ua, ip)
    session = UserSession(
        user_id=current_user.id,
        device_fingerprint=fingerprint,
        ip_address=ip,
        user_agent=ua,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_trusted=True
    )
    db.add(session)
    await db.commit()
    return {"message": "Device marked as trusted", "fingerprint": fingerprint}