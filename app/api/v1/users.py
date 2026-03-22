from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID  # <-- Added this import

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import User
from app.schemas.schemas import UserCreate, UserResponse
from app.api.v1.auth import pwd_context

router = APIRouter()


def verify_superuser_role(current_user: dict = Depends(get_current_active_user)):
    """Ensures only executive roles can create or modify user accounts."""
    if current_user.get("role") not in ["SysAdmin", "Bishop", "Vicar General"]:
        raise HTTPException(status_code=403, detail="Unauthorized. Only Curia executives can manage accounts.")
    return current_user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db),
        admin_user: dict = Depends(verify_superuser_role)
):
    # 1. Check if email already exists
    existing_user = await db.execute(select(User).where(User.email == user_in.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    # 2. Hash the password before saving
    hashed_password = pwd_context.hash(user_in.password)

    # 3. Create the database record
    new_user = User(
        email=user_in.email,
        password_hash=hashed_password,
        role=user_in.role,
        office=user_in.office,
        parish_id=user_in.parish_id,
        deanery_id=user_in.deanery_id,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """Allows a logged-in user to fetch their own profile details."""

    # Safely convert the JWT string back into a strict UUID object for PostgreSQL
    try:
        user_uuid = UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid User ID format in token.")

    query = await db.execute(select(User).where(User.id == user_uuid))
    user = query.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user