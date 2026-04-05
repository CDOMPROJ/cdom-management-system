from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pyotp
import uuid

# Secure internal imports
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import User
from app.schemas.old_schemas import LoginRequest, LoginResponse, MFAVerifyRequest

router = APIRouter()


# ==============================================================================
# 1. THE LOGIN ENDPOINT (MFA INTERCEPTOR)
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
# 2. MFA VERIFICATION ENDPOINT
# ==============================================================================
@router.post("/verify-mfa", response_model=LoginResponse)
async def verify_mfa(request: MFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Validates the 6-digit Authenticator code and issues the final JWT."""
    from app.core.security import decode_access_token

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