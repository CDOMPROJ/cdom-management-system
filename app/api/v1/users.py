from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import secrets

# Core dependencies and security utilities
from app.core.dependencies import get_db, require_sysadmin_access
from app.core.security import get_password_hash
from app.core.email import send_invitation_email

# Database Models and Pydantic Schemas
from app.models.all_models import User, UserInvitationModel
from app.schemas.schemas import UserInviteRequest, UserSetupRequest

router = APIRouter()

# ==============================================================================
# 1. SYSADMIN: INVITE NEW USER (ZERO TRUST PROVISIONING)
# ==============================================================================
@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: UserInviteRequest,
    db: AsyncSession = Depends(get_db),
    _sysadmin: dict = Depends(require_sysadmin_access) # SECURITY: ONLY SysAdmin can trigger this
):
    """
    SysAdmin provisions an account slot.
    Generates a secure token and emails the user via Resend to their personal email
    so they can set their own password for their official CDOM office account.
    """
    # 1. Check if user already exists in the main table
    query = select(User).where(User.email == request.email)
    existing_user = (await db.execute(query)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this office email already exists.")

    # 2. Check if an invitation is already pending
    query_invite = select(UserInvitationModel).where(UserInvitationModel.email == request.email)
    existing_invite = (await db.execute(query_invite)).scalar_one_or_none()
    if existing_invite:
        await db.delete(existing_invite) # Delete the old one to issue a fresh token
        await db.flush()

    # 3. Generate Secure Token & Expiration (Valid for 48 hours)
    invite_token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(hours=48)

    # 4. Save the invitation to the Database using the OFFICIAL email
    new_invite = UserInvitationModel(
        email=request.email,
        role=request.role,
        parish_id=request.parish_id,
        deanery_id=request.deanery_id,
        token=invite_token,
        expires_at=expiration
    )
    db.add(new_invite)
    await db.commit()

    # 5. Send the HTML Invitation Email to the PERSONAL inbox
    email_sent = send_invitation_email(
        to_email=request.personal_email, # <--- ROUTED TO PERSONAL GMAIL
        role=request.role,
        invite_token=invite_token
    )

    if not email_sent:
        # If Resend fails (e.g., bad API key), we still return a 201 but provide the token
        # in the response so you can test it manually without getting blocked.
        return {
            "message": f"Invitation generated for {request.email}, but there was an error sending the email to {request.personal_email}.",
            "token": invite_token
        }

    return {"message": f"Invitation successfully generated and sent to {request.personal_email} for office {request.email}"}


# ==============================================================================
# 2. PUBLIC: USER COMPLETES ACCOUNT SETUP
# ==============================================================================
@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def complete_user_setup(
    request: UserSetupRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    The invited user submits their personal details and private password.
    Consumes the token, hashes the password, and creates the actual User record.
    """
    # 1. Verify the Token exists in the database
    query = select(UserInvitationModel).where(UserInvitationModel.token == request.token)
    invite = (await db.execute(query)).scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or unrecognized invitation token.")

    # 2. Check Expiration
    if invite.expires_at < datetime.now(timezone.utc):
        await db.delete(invite)
        await db.commit()
        raise HTTPException(status_code=400, detail="This invitation has expired. Contact the SysAdmin for a new one.")

    # 3. Create the Actual User Record
    # Note: request.first_name and request.last_name are captured here.
    # They will be saved to the database once those columns are added in the next Alembic migration.
    new_user = User(
        email=invite.email,
        password_hash=get_password_hash(request.password), # Cryptographically hashed!
        role=invite.role,
        parish_id=invite.parish_id,
        deanery_id=invite.deanery_id,
        is_active=True,
        mfa_enabled=False # User will be prompted to set up TOTP on their first login
    )
    db.add(new_user)

    # 4. Burn the Invitation (Tokens are strictly one-time use to prevent replay attacks)
    await db.delete(invite)
    await db.commit()

    return {"message": "Account setup complete. You may now log in."}


# ==============================================================================
# 3. SYSADMIN: DELETE / RECLAIM ACCOUNT
# ==============================================================================
@router.delete("/{email}", status_code=status.HTTP_200_OK)
async def delete_user(
    email: str,
    db: AsyncSession = Depends(get_db),
    _sysadmin: User = Depends(require_sysadmin_access) # SECURITY: ONLY SysAdmin
):
    """
    SysAdmin evicts a user from an office account.
    Deletes the record so the @domansa.org email can be re-provisioned to a new physical person.
    """
    # 1. Protect the master key!
    if email == "sysadmin@domansa.org":
        raise HTTPException(status_code=400, detail="Cannot delete the master SysAdmin account.")

    # 2. Find the user
    query = select(User).where(User.email == email)
    user = (await db.execute(query)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found in the database.")

    # 3. Delete the user
    await db.delete(user)
    await db.commit()

    return {"message": f"Account {email} has been completely deleted and reclaimed."}
