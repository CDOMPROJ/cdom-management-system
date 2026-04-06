# ==============================================================================
# app/api/v1/clergy_registry.py
# Clergy Registry Router – Bishop-only + Ownership Enforcement
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.models.all_models import ClergyRegistryModel
from app.schemas.schemas import ClergyRegistryCreate, ClergyRegistryResponse
from typing import List

router = APIRouter(prefix="/clergy-registry", tags=["clergy-registry"])

ownership_service = OwnershipService()

@router.get("/", response_model=List[ClergyRegistryResponse])
async def get_clergy_registry(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop has access to the clergy registry")
    result = await db.execute(select(ClergyRegistryModel))
    return result.scalars().all()

@router.post("/", response_model=ClergyRegistryResponse)
async def create_clergy_registry(
    clergy_data: ClergyRegistryCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can create clergy registry entries")
    clergy = ClergyRegistryModel(**clergy_data.dict(), owner_user_id=current_user.id)
    db.add(clergy)
    await db.commit()
    await db.refresh(clergy)
    return clergy