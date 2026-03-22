import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.dependencies import get_db
from app.models.all_models import User, ParishModel
from app.schemas.schemas import UserCreate, UserResponse, Token

router = APIRouter()

# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================
# In production, move these to a secure .env file!
SECRET_KEY = "cdom_super_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against the stored database hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a plain text password for secure database storage."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates the JWT and embeds the user's canonical clearance data."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ==============================================================================
# 1. PERSONNEL REGISTRATION (SYSADMIN / GENESIS CONTROLLED)
# ==============================================================================
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db),
        authorization: Optional[str] = Header(None)
):
    """
    Registers a new diocesan user.
    - GENESIS BOOT: If the database has 0 users, it allows anyone to create the first admin.
    - SYSADMIN GATE: If users exist, it strictly requires a valid JWT from the Curia.
    """
    # Always register users into the public identity schema
    await db.execute(text('SET search_path TO public'))

    # 1. Count existing users to check for the Genesis Boot phase
    user_count_query = await db.execute(select(func.count(User.id)))
    user_count = user_count_query.scalar() or 0

    # 2. SysAdmin Security Gate (Triggered if the DB is already initialized)
    if user_count > 0:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="SysAdmin authorization required to provision new users."
            )

        token = authorization.split(" ")[1]
        try:
            # Decode token to verify the creator holds a Curia rank
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            creator_role = payload.get("role")

            if creator_role not in ["SysAdmin", "Bishop"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Only Curia or SysAdmins can provision new personnel accounts."
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired admin token."
            )

    # 3. Check for Email Duplication
    query = await db.execute(select(User).where(User.email == user_in.email.lower()))
    if query.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this official CDOM email already exists."
        )

    # 4. Create and Persist the User
    new_user = User(
        email=user_in.email.lower(),
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        office=user_in.office,
        parish_id=user_in.parish_id,
        deanery_id=user_in.deanery_id
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


# ==============================================================================
# 2. LOGIN & SINGLE SESSION GENERATION
# ==============================================================================
@router.post("/login", response_model=Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    """
    Authenticates the user, determines their canonical schema, and
    enforces the Single Active Session rule by generating a new Session UUID.
    """
    await db.execute(text('SET search_path TO public'))

    # 1. Verify Credentials
    query = await db.execute(select(User).where(User.email == form_data.username.lower()))
    user = query.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account deactivated by the Diocesan Curia."
        )

    # 2. [CRITICAL SECURITY] Enforce Single Active Session
    # Generating a new UUID invalidates any token operating on the old UUID
    new_session_id = str(uuid.uuid4())
    user.session_id = new_session_id
    await db.commit()

    # 3. Tenant Routing: Determine where this user's queries should default to
    schema_name = "public"
    if user.parish_id:
        parish_query = await db.execute(select(ParishModel).where(ParishModel.id == user.parish_id))
        parish = parish_query.scalar_one_or_none()
        if parish:
            schema_name = parish.schema_name

    # 4. Bake Identity & Clearance into the JWT Payload
    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": user.role,
            "parish_id": user.parish_id,
            "deanery_id": user.deanery_id,
            "tenant_schema": schema_name,
            "session_id": new_session_id
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {"access_token": access_token, "token_type": "bearer"}