from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
import pyotp
import uuid

# Assuming you have a security utilities file for hashing and JWT creation
# If not, you will need to implement verify_password and create_access_token.
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_db, get_current_user
from app.models.all_models import User
from app.schemas.schemas import LoginRequest, LoginResponse, MFASetupResponse, MFAVerifyRequest
from app.core.config import settings

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
    # 1. Fetch User
    query = select(User).where(User.email == credentials.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")

    # 2. Construct Base Payload
    jwt_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "parish_id": user.parish_id
    }

    # 3. MFA Interceptor
    if user.mfa_enabled:
        # Issue a temporary token strictly for the /login/mfa endpoint (valid for 5 mins)
        temp_token = create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=5))
        return LoginResponse(
            mfa_required=True,
            temp_token=temp_token,
            message="MFA required. Please submit your 6-digit Authenticator code."
        )

    # 4. Standard Flow (No MFA setup yet)
    access_token = create_access_token(data=jwt_payload)
    return LoginResponse(
        access_token=access_token,
        mfa_required=False,
        message="Login successful."
    )


# ==============================================================================
# 2. MFA SETUP (GENERATE SECRET & QR CODE)
# ==============================================================================
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Generates a secure Base32 secret and provisioning URI for Google Authenticator.
    Does NOT enable MFA until the user verifies their first code.
    """
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled.")

    # Generate the cryptographic seed
    secret = pyotp.random_base32()

    # Save it to the database, but keep mfa_enabled = False
    current_user.mfa_secret = secret
    await db.commit()

    # Create the specialized URI that QR code generators expect
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="CDOM Registry"
    )

    return MFASetupResponse(secret=secret, provisioning_uri=provisioning_uri)


# ==============================================================================
# 3. MFA ENABLE (VERIFY FIRST CODE)
# ==============================================================================
@router.post("/mfa/enable")
async def enable_mfa(request: MFAVerifyRequest, current_user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """
    Validates the user's first TOTP code. If correct, locks MFA to 'Enabled'.
    """
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA setup has not been initiated.")

    totp = pyotp.TOTP(current_user.mfa_secret)

    # Verify the code (usually valid for a 30-second window)
    if not totp.verify(request.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code. Please try again.")

    # Success! Lock down the account.
    current_user.mfa_enabled = True
    await db.commit()

    return {"message": "Multi-Factor Authentication is now actively protecting your account."}


# ==============================================================================
# 4. MFA LOGIN VERIFICATION
# ==============================================================================
@router.post("/login/mfa", response_model=LoginResponse)
async def verify_mfa_login(request: MFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    """
    The second step of the login flow. Validates the temp_token and the 6-digit code.
    """
    if not request.temp_token:
        raise HTTPException(status_code=400, detail="Temporary authentication token required.")

    # In a real setup, you decode the temp_token here to extract the user's ID
    # user_id = decode_jwt_token(request.temp_token).get("sub")

    # Placeholder: Assuming you have a function that extracts the user ID from the temp token
    # For now, let's pretend we extracted it successfully. You'll need your `decode_access_token` function here.
    from app.core.security import decode_access_token
    payload = decode_access_token(request.temp_token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired temporary token.")

    user_id = payload.get("sub")

    # Fetch User
    query = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not configured for this user.")

    # Verify the TOTP Math!
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(request.code):
        raise HTTPException(status_code=401, detail="Invalid authentication code.")

    # Re-issue the FULL, standard access token now that identity is proven
    jwt_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "parish_id": user.parish_id
    }

    access_token = create_access_token(data=jwt_payload)

    return LoginResponse(
        access_token=access_token,
        mfa_required=False,
        message="MFA Verification successful. Welcome."
    )