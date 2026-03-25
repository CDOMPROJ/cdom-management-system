from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pyotp
import uuid
import secrets
from datetime import datetime, timedelta, timezone

# Secure internal imports
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import User
from app.schemas.schemas import LoginRequest, LoginResponse, MFAVerifyRequest
from app.schemas.schemas import ForgotPasswordRequest, ResetPasswordRequest
from app.core.email import send_password_reset_email
from app.core.security import get_password_hash

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


# ==============================================================================
# 3. FORGOT PASSWORD (REQUEST RESET)
# ==============================================================================
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
        request: ForgotPasswordRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db)
):
    """Generates a secure, 1-hour expiry token and emails the reset link."""
    query = select(User).where(User.email == request.email)
    user = (await db.execute(query)).scalar_one_or_none()

    # SECURITY BEST PRACTICE: Always return a generic success message to prevent
    # malicious actors from using this endpoint to guess which emails exist in the DB.
    if user:
        # Generate token and expiry
        raw_token = secrets.token_urlsafe(32)
        user.reset_token = raw_token
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()

        # Dispatch email in the background
        reset_link = f"https://domansa.org/reset-password?token={raw_token}"
        background_tasks.add_task(send_password_reset_email, email_to=user.email, reset_url=reset_link)

    return {"message": "If an account with that email exists, a password reset link has been sent."}


# ==============================================================================
# 4. RESET PASSWORD (CONFIRM NEW PASSWORD)
# ==============================================================================
@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
        request: ResetPasswordRequest,
        db: AsyncSession = Depends(get_db)
):
    """Verifies the token and updates the user's password."""
    query = select(User).where(User.reset_token == request.token)
    user = (await db.execute(query)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # Check expiration
    if user.reset_token_expires is None or datetime.now(timezone.utc) > user.reset_token_expires:
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    # Apply new password
    user.password_hash = get_password_hash(request.new_password)

    # Burn the token so it cannot be used again
    user.reset_token = None
    user.reset_token_expires = None

    await db.commit()

    return {"message": "Password successfully reset. You may now log in with your new password."}