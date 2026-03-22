from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from jose import JWTError, jwt

from app.models.all_models import AuditLogModel, PendingActionModel, User

# ==============================================================================
# DATABASE & SECURITY CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
SECRET_KEY = "cdom_super_secret_key_change_in_production"
ALGORITHM = "HS256"

async def get_db():
    """Yields a fresh, asynchronous database connection for each request."""
    async with AsyncSessionLocal() as session:
        yield session

# ==============================================================================
# 1. JWT DECODING & SINGLE SESSION VERIFICATION
# ==============================================================================
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Decodes the JWT, checks for parallel logins, and sets the DB search_path
    so the user is securely locked into their specific Parish Schema.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        session_id: str = payload.get("session_id")
        tenant_schema: str = payload.get("tenant_schema")

        if not email or not session_id or not tenant_schema:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Enforce Single Active Login Constraint (Public Schema Check)
    await db.execute(text('SET search_path TO public'))
    user_query = await db.execute(select(User).where(User.email == email))
    db_user = user_query.scalar_one_or_none()

    if not db_user or db_user.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session Invalidated: You have logged into another device."
        )

    user_data = {
        "email": db_user.email,
        "role": db_user.role,
        "parish_id": db_user.parish_id,
        "deanery_id": db_user.deanery_id,
        "tenant_schema": tenant_schema
    }

    # Physical switch to the isolated Parish database schema (Bishop role bypass handled in routers)
    await db.execute(text(f'SET search_path TO "{tenant_schema}", public'))
    return user_data

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Alias for backwards compatibility with existing routers."""
    return current_user

# ==============================================================================
# 2. ROLE-BASED ACCESS CONTROL (RBAC) GATES
# ==============================================================================
def require_read_access(user: dict = Depends(get_current_active_user)):
    """STRICT ENFORCEMENT: SysAdmins are fundamentally barred from reading pastoral data."""
    if user["role"] == "SysAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zero Trust Violation: SysAdmins are not authorized to view pastoral or sacramental data."
        )
    return user

def require_create_access(user: dict = Depends(get_current_active_user)):
    """Parish Secretaries, APs, PPs, and YCs can create canonical records."""
    allowed_roles = ["Parish Secretary", "Assistant Priest", "Parish Priest", "Parish Youth Chaplain"]
    if user["role"] not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only Parish Administration can create canonical records."
        )
    return user

def require_modify_access(user: dict = Depends(get_current_active_user)):
    """APs and PPs can initiate modifications."""
    if user["role"] not in ["Assistant Priest", "Parish Priest"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You do not have permissions to modify canonical records."
        )
    return user

def require_youth_chaplain(user: dict = Depends(get_current_active_user)):
    """Only allows Parish Youth Chaplains or PPs."""
    if user["role"] not in ["Parish Youth Chaplain", "Parish Priest"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Youth Ministry Access Only."
        )
    return user

def require_parish_priest(user: dict = Depends(get_current_active_user)):
    """Strictly reserved for the Parish Priest."""
    if user["role"] != "Parish Priest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Strictly reserved for the Parish Priest."
        )
    return user

def require_sysadmin_access(user: dict = Depends(get_current_active_user)):
    """SysAdmin strictly for provisioning accounts."""
    if user["role"] != "SysAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: SysAdmin access required to provision accounts."
        )
    return user

def require_bishop_access(user: dict = Depends(get_current_active_user)):
    """Exclusive gate for the Bishop of CDOM."""
    if user["role"] != "Bishop":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Exclusive access granted only to the Bishop of CDOM."
        )
    return user

# ==============================================================================
# 3. GOVERNANCE UTILITIES (AUDIT & APPROVAL QUEUES)
# ==============================================================================
async def process_modification_request(
        db: AsyncSession, user: dict, action_type: str, table_name: str, record_id: str, payload: dict
):
    """Core Governance Logic: AP -> Queue, PP -> Execute."""
    if user["role"] == "Assistant Priest":
        pending = PendingActionModel(
            requested_by=user["email"], action_type=action_type, target_table=table_name,
            target_record_id=str(record_id), proposed_payload=payload
        )
        db.add(pending)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Modification queued. Awaiting Parish Priest approval."
        )

    elif user["role"] == "Parish Priest":
        audit = AuditLogModel(
            user_email=user["email"], action=action_type, table_name=table_name,
            record_id=str(record_id), changes=payload
        )
        db.add(audit)
        return True