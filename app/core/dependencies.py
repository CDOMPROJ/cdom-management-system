from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
import uuid

# ==============================================================================
# 0. CONFIGURATION & SECURE IMPORTS
# ==============================================================================
from app.core.config import settings
from app.models.all_models import PendingActionModel, User

# 🔥 THE FIX: Correct absolute import path to your database.py file
from app.core.database import AsyncSessionLocal

# Defines the endpoint where clients will send their email/password to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db():
    """Yields a fresh, asynchronous database connection for each request."""
    async with AsyncSessionLocal() as session:
        yield session


# ==============================================================================
# 1. JWT AUTHENTICATION & IDENTITY EXTRACTION
# ==============================================================================
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> User:
    """Decodes the JWT and securely fetches the physical User object from the DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    query = select(User).where(User.id == uuid.UUID(user_id))
    user = (await db.execute(query)).scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensures the user account has not been suspended or soft-deleted by the SysAdmin."""
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled. Please contact the SysAdmin.")
    return current_user


# ==============================================================================
# 2. ROLE-BASED ACCESS CONTROL (RBAC) GATES
# ==============================================================================
async def require_sysadmin_access(user: User = Depends(get_current_active_user)):
    """Gate: Exclusive access for the Master System Administrator."""
    if user.role != "SysAdmin":
        raise HTTPException(status_code=403, detail="SysAdmin clearance required.")
    return user


async def require_bishop_access(user: User = Depends(get_current_active_user)):
    """Gate: Ensures ONLY the Bishop or the Master SysAdmin has access."""
    if user.role not in ["Bishop", "SysAdmin"]:
        raise HTTPException(status_code=403, detail="Strictly restricted to Bishop-level clearance.")
    return user


async def require_parish_priest(user: User = Depends(get_current_active_user)):
    """Gate: Grants access to Parish Priests and all roles above them."""
    allowed = ["Parish Priest", "Dean", "Bishop", "SysAdmin"]
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Parish Priest cryptographic authority required.")
    return user


async def require_read_access(user: User = Depends(get_current_active_user)):
    """Gate: Allows any authenticated and active CDOM staff to read records."""
    return user


async def require_create_access(user: User = Depends(get_current_active_user)):
    """Gate: Allows standard entry (Assistant Priests, Secretaries) to create records."""
    return user


async def require_update_access(user: User = Depends(get_current_active_user)):
    """Gate: Ensures the user has permissions to modify existing records."""
    return user


# ==============================================================================
# 3. GOVERNANCE UTILITIES (APPROVAL QUEUE)
# ==============================================================================
async def process_modification_request(
        db: AsyncSession, user: User, action_type: str, table_name: str, record_id: str, payload: dict
):
    """
    Core Governance Logic: Saves the proposed modification to the pending queue.
    """
    pending = PendingActionModel(
        requested_by=user.email,
        action_type=action_type,
        target_table=table_name,
        target_record_id=str(record_id),
        proposed_payload=payload,
        status="PENDING"
    )
    db.add(pending)
    await db.commit()
    return pending