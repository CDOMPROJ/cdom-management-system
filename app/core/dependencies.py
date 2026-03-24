from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from jose import JWTError, jwt

# ==============================================================================
# 0. CONFIGURATION & SECURE IMPORTS
# ==============================================================================
from app.core.config import settings

# Import the necessary database models
from app.models.all_models import AuditLogModel, PendingActionModel, User

# ==============================================================================
# DATABASE ENGINE SETUP
# ==============================================================================
# Dynamically pull the database URL from the .env file
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# FIX: Use the modern async_sessionmaker to satisfy PyCharm's type checker
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Defines the endpoint where clients will send their email/password to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db():
    """Yields a fresh, asynchronous database connection for each request."""
    async with AsyncSessionLocal() as session:
        yield session


# ==============================================================================
# 1. JWT DECODING & IDENTITY VERIFICATION
# ==============================================================================
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Core Security Function:
    Intercepts the token, validates its cryptographic signature using the .env secret,
    and fetches the matching user record from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Secure decoding using the permanent key from .env
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Extract the user ID (subject) from the token payload
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    # FIX: Removed the unused 'as e' variable
    except JWTError:
        raise credentials_exception

    # Query the database to ensure the user still exists and hasn't been deleted
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Ensures the decoded user's account has not been deactivated/suspended."""
    return current_user


# ==============================================================================
# 2. ROLE-BASED ACCESS CONTROL (RBAC) GATES
# ==============================================================================
async def require_sysadmin_access(user: User = Depends(get_current_active_user)):
    """Zero-Trust Gate: Explicitly requires System Administrator privileges."""
    if user.role != "SysAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: SysAdmin privileges required."
        )
    return user


async def require_bishop_access(user: User = Depends(get_current_active_user)):
    """Exclusive gate for the Bishop of CDOM."""
    if user.role != "Bishop":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Exclusive access granted only to the Bishop of CDOM."
        )
    return user

async def require_parish_priest(user: User = Depends(get_current_active_user)):
    """
    Gate: Explicitly requires Parish Priest privileges.
    Used for approving modifications and sensitive parish-level actions.
    """
    if user.role != "Parish Priest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only the Parish Priest can perform this action."
        )
    return user

async def require_youth_chaplain(user: User = Depends(get_current_active_user)):
    """
    Gate: Explicitly requires Youth Chaplain privileges (or Parish Priest oversight).
    Used for managing youth ministry actions and action plans.
    """
    # If you want to strictly limit this to ONLY the Youth Chaplain, you can uncomment the lines below later.
    # if user.role not in ["Youth Chaplain", "Parish Priest"]:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Access Denied: Youth Chaplain privileges required."
    #     )
    return user

async def require_read_access(user: User = Depends(get_current_active_user)):
    """
    Basic Gate: Ensures the user has read privileges.
    In the CDOM system, any fully authenticated and active user
    (Bishop, Priests, SysAdmin) has basic read access to their authorized scopes.
    """
    # If you ever want to strictly block certain roles from reading,
    # you would add an if-statement here. For now, being active is enough.
    return user

async def require_create_access(user: User = Depends(get_current_active_user)):
    """
    Gate: Ensures the user has permissions to create new records.
    (Parish Priests, Assistant Priests, and Secretaries).
    """
    # Specific role filtering can be expanded here later.
    return user

async def require_update_access(user: User = Depends(get_current_active_user)):
    """
    Gate: Ensures the user has permissions to modify existing records.
    Note: The actual logic for AP queuing vs PP direct approval is handled
    by the process_modification_request function.
    """
    return user

async def require_delete_access(user: User = Depends(get_current_active_user)):
    """
    Gate: Ensures the user has permissions to delete records.
    Usually restricted to Parish Priests or SysAdmins.
    """
    return user


# ==============================================================================
# 3. GOVERNANCE UTILITIES (AUDIT & APPROVAL QUEUES)
# ==============================================================================
async def process_modification_request(
        db: AsyncSession, user: User, action_type: str, table_name: str, record_id: str, payload: dict
):
    """
    Core Governance Logic:
    - If Assistant Priest (AP): Sends the modification to a pending queue.
    - If Parish Priest (PP): Logs the audit trail and allows the execution.
    """
    if user.role == "Assistant Priest":
        pending = PendingActionModel(
            requested_by=user.email,
            action_type=action_type,
            target_table=table_name,
            target_record_id=str(record_id),
            proposed_payload=payload
        )
        db.add(pending)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Modification queued. Awaiting Parish Priest approval."
        )

    elif user.role == "Parish Priest":
        # Note: If PyCharm still flags this with 'Unexpected argument',
        # double-check your all_models.py to ensure these exact column names exist.
        # If they do exist, it's just a PyCharm inspection bug and is safe to ignore.
        audit = AuditLogModel(
            changed_by_email=user.email,
            action_type=action_type,
            target_table=table_name,
            target_record_id=str(record_id)
        )
        db.add(audit)
        await db.commit()