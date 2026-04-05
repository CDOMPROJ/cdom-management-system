from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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
from app.schemas.old_schemas import UserInviteRequest, UserSetupRequest, DirectUserCreateRequest

router = APIRouter()

# ==============================================================================
# 1. SYSADMIN: INVITE NEW USER (ZERO TRUST PROVISIONING)
# ==============================================================================
@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: UserInviteRequest,
    background_tasks: BackgroundTasks, # <-- Inject the Background Worker
    db: AsyncSession = Depends(get_db),
    _sysadmin: User = Depends(require_sysadmin_access) # SECURITY: Strict User object
):
    """
    SysAdmin provisions an account slot.
    Generates a secure token and queues an email via Resend in the background.
    """
    # 1. Check if user already exists
    query = select(User).where(User.email == request.email)
    existing_user = (await db.execute(query)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in the system.")

    # 2. Generate secure token
    raw_token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(hours=48)

    # 3. Save invitation to DB
    new_invite = UserInvitationModel(
        email=request.email,
        token=raw_token,
        role=request.role,
        office=request.office,
        parish_id=request.parish_id,
        deanery_id=request.deanery_id,
        expires_at=expiration
    )
    db.add(new_invite)
    await db.commit()

    # 4. Dispatch the setup email silently in the background
    setup_link = f"https://domansa.org/setup?token={raw_token}"
    background_tasks.add_task(
        send_invitation_email,
        email_to=request.email,
        setup_url=setup_link
    )

    return {"message": f"Invitation queued and will be sent to {request.email}."}

# ==============================================================================
# 2. SYSADMIN: DELETE / RECLAIM ACCOUNT
# ==============================================================================
@router.delete("/{email}", status_code=status.HTTP_200_OK)
async def delete_user(
    email: str,
    db: AsyncSession = Depends(get_db),
    _sysadmin: User = Depends(require_sysadmin_access) # SECURITY: Strict User object
):
    """
    SysAdmin evicts a user from an office account.
    Soft-deletes the record so the @domansa.org email can be re-provisioned.
    """
    if email == "sysadmin@domansa.org":
        raise HTTPException(status_code=400, detail="Cannot disable the master SysAdmin account.")

    query = select(User).where(User.email == email)
    user = (await db.execute(query)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # SOFT DELETE: We disable the account instead of dropping the row,
    # ensuring financial audit logs tied to this User.id do not break.
    user.is_active = False
    await db.commit()

    return {"message": f"Account {email} has been successfully deactivated."}


# ==============================================================================
# 1.5. SYSADMIN: DIRECT ACCOUNT CREATION (DEV / FAST PROVISIONING)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user_directly(
        request: DirectUserCreateRequest,
        db: AsyncSession = Depends(get_db),
        _sysadmin: User = Depends(require_sysadmin_access)  # SECURITY: Must be SysAdmin
):
    """
    Directly creates an active user without the email invitation flow.
    Perfect for initial system provisioning or local development.
    """
    # Check if user exists
    query = select(User).where(User.email == request.email)
    existing_user = (await db.execute(query)).scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")

    # Create the user directly
    new_user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        role=request.role,
        office=request.office,
        parish_id=request.parish_id,
        deanery_id=request.deanery_id,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"message": f"Account for {request.email} created and activated successfully."}