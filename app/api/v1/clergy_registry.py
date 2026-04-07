# ==============================================================================
# app/api/v1/clergy_registry.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import uuid
from typing import Any, Dict

from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import ClergyRegistryModel, User
from app.schemas.schemas import ClergyRegistryCreate

router = APIRouter()

ownership_service = OwnershipService()


# ==============================================================================
# 1. REGISTER CLERGY (BISHOP-ONLY)
# ==============================================================================
@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_clergy_registry(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("bishop:read")(current_user)  # Only Bishop has full access
    query = select(ClergyRegistryModel).order_by(desc(ClergyRegistryModel.date_of_ordination)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_clergy(
    clergy_in: ClergyRegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can register clergy in the official registry.")

    await ownership_service.check_ownership(clergy_in, current_user)

    current_year = clergy_in.date_of_ordination.year
    query = await db.execute(
        select(func.max(ClergyRegistryModel.row_number)).where(ClergyRegistryModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        new_clergy = ClergyRegistryModel(
            **clergy_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number,
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(new_clergy)
        await db.commit()
        await db.refresh(new_clergy)

        return {
            "message": "Clergy registered successfully under Episcopal authority.",
            "canonical_reference": canonical_number,
            "id": str(new_clergy.id)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# ==============================================================================
# 2. UPDATE CLERGY (BISHOP-ONLY GOVERNANCE)
# ==============================================================================
@router.put("/{clergy_id}", status_code=status.HTTP_200_OK)
async def update_clergy(
    clergy_id: uuid.UUID,
    payload: ClergyRegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can update the clergy registry.")

    query = select(ClergyRegistryModel).where(ClergyRegistryModel.id == clergy_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()
    if not existing_record:
        raise HTTPException(status_code=404, detail="Clergy record not found.")

    await ownership_service.check_ownership(existing_record, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing_record, key, value)
    await db.commit()

    return {"message": "Clergy record updated successfully under Episcopal authority."}