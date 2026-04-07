# ==============================================================================
# app/api/v1/confirmation.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
import uuid
from typing import Any, Dict

from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import ConfirmationModel, GlobalRegistryIndex, User
from app.schemas.schemas import ConfirmationCreate

router = APIRouter()

ownership_service = OwnershipService()


# ==============================================================================
# 1. REGISTER CONFIRMATION (CANONICAL DATA ENTRY)
# ==============================================================================
@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_recent_confirmations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:read")(current_user)
    query = select(ConfirmationModel).order_by(desc(ConfirmationModel.confirmation_date)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_confirmation(
    confirmation_in: ConfirmationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:write")(current_user)
    await ownership_service.check_ownership(confirmation_in, current_user)

    current_year = confirmation_in.confirmation_date.year
    query = await db.execute(
        select(func.max(ConfirmationModel.row_number)).where(ConfirmationModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        new_conf = ConfirmationModel(
            **confirmation_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number,
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(new_conf)
        await db.flush()

        global_entry = GlobalRegistryIndex(
            first_name=confirmation_in.first_name,
            last_name=confirmation_in.last_name,
            canonical_number=canonical_number,
            record_type="CONFIRMATION",
            parish_id=current_user.parish_id,
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(global_entry)
        await db.commit()

        return {
            "message": "Confirmation registered successfully.",
            "canonical_reference": canonical_number,
            "id": str(new_conf.id)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# ==============================================================================
# 2. LOCAL SEARCH (TYPO-TOLERANT FUZZY SEARCH)
# ==============================================================================
@router.get("/search")
async def search_confirmations(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:read")(current_user)
    result = await db.execute(select(ConfirmationModel))
    rows = result.scalars().all()
    if not rows:
        return {"results": [], "message": "No records found."}

    search_strings = [f"{r.first_name} {r.last_name} {r.formatted_number}".lower() for r in rows]
    record_map = rows
    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)
    results = [record_map[idx] for _, _, idx in matches]
    return {"query": q, "match_count": len(results), "results": results}


# ==============================================================================
# 3. UPDATE CONFIRMATION (GOVERNANCE WORKFLOW)
# ==============================================================================
@router.put("/{confirmation_id}", status_code=status.HTTP_200_OK)
async def update_confirmation(
    confirmation_id: uuid.UUID,
    payload: ConfirmationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:write")(current_user)

    query = select(ConfirmationModel).where(ConfirmationModel.id == confirmation_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()
    if not existing_record:
        raise HTTPException(status_code=404, detail="Confirmation record not found.")

    await ownership_service.check_ownership(existing_record, current_user)

    if current_user.office.value != "Parish Priest":
        await process_modification_request(
            db=db, user=current_user, action_type="UPDATE",
            table_name="confirmations", record_id=str(confirmation_id),
            payload=payload.model_dump(mode='json')
        )
        return JSONResponse(status_code=202, content={"message": "Modification queued. Awaiting Parish Priest approval."})

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing_record, key, value)
    await db.commit()

    return {"message": "Confirmation record updated successfully."}