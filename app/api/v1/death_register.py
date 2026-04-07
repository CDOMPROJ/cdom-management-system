# ==============================================================================
# app/api/v1/death_register.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from typing import Dict, Any

from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
import uuid

from app.core.dependencies import process_modification_request
# PHASE 3 SECURE IMPORTS (consolidated – no old dependencies folder)
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import DeathRegisterModel, BaptismModel, GlobalRegistryIndex, User
from app.schemas.schemas import DeathRegisterCreate

router = APIRouter()

# Phase 3 Ownership Service
ownership_service = OwnershipService()


# ==============================================================================
# 1. REGISTER DEATH (WITH AUTOMATED BAPTISM LINKING)
# ==============================================================================
@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_recent_deaths(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("parish:read")(current_user)

    query = select(DeathRegisterModel).order_by(desc(DeathRegisterModel.date_of_death)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_death(
        death_in: DeathRegisterCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Registers a death and creates a shadow entry in the Global CDOM Index.
    If a baptism_number is provided, it automatically marks the local Baptism record as deceased.
    """
    # PHASE 3 ABAC + OWNERSHIP ENFORCEMENT
    await PermissionChecker("parish:write")(current_user)
    await ownership_service.check_ownership(death_in, current_user)

    current_year = death_in.date_of_death.year

    # 1. Generate Canonical Number
    query = await db.execute(
        select(func.max(DeathRegisterModel.row_number)).where(DeathRegisterModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        # 2. Save Death Record
        new_death = DeathRegisterModel(
            **death_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number,
            # PHASE 3 OWNERSHIP COLUMNS (added – old logic untouched)
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(new_death)
        await db.flush()  # Flush to generate the UUID for cross-linking

        # 3. Canonical Cross-Linking (Automated Baptism Update)
        if death_in.baptism_number:
            bap_query = select(BaptismModel).where(BaptismModel.formatted_number == death_in.baptism_number)
            bap_record = (await db.execute(bap_query)).scalar_one_or_none()

            if bap_record:
                bap_record.is_deceased = True
                bap_record.death_record_id = new_death.id

        # 4. Global Diocesan Indexing
        global_entry = GlobalRegistryIndex(
            first_name=new_death.first_name,
            last_name=new_death.last_name,
            canonical_number=canonical_number,
            baptism_number=new_death.baptism_number,
            record_type="DEATH",
            parish_id=current_user.parish_id,
            # PHASE 3 OWNERSHIP COLUMNS (added – old logic untouched)
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(global_entry)

        await db.commit()

        return {
            "message": "Death registered and canonical cross-references updated successfully.",
            "canonical_reference": canonical_number,
            "id": str(new_death.id)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# ==============================================================================
# 2. LOCAL SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/search")
async def search_deaths(
        q: str = Query(..., min_length=2),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("parish:read")(current_user)

    result = await db.execute(select(DeathRegisterModel))
    rows = result.scalars().all()

    if not rows:
        return {"results": [], "message": "No records found."}

    search_strings, record_map = [], []
    for record in rows:
        middle = record.middle_name or ""
        bap_num = record.baptism_number or ""
        search_data = f"{record.first_name} {middle} {record.last_name} {record.formatted_number} {bap_num}".lower()
        search_strings.append(search_data)
        record_map.append(record)

    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)
    return {"query": q, "match_count": len(matches), "results": [record_map[idx] for _, _, idx in matches]}


# ==============================================================================
# 3. UPDATE DEATH RECORD (GOVERNANCE WORKFLOW)
# ==============================================================================
@router.put("/{record_id}", status_code=status.HTTP_200_OK)
async def update_death(
        record_id: uuid.UUID,
        payload: DeathRegisterCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Modifies a death record, protected by the Parish Priest Governance Queue.
    """
    # PHASE 3 ABAC + OWNERSHIP ENFORCEMENT
    await PermissionChecker("parish:write")(current_user)

    query = select(DeathRegisterModel).where(DeathRegisterModel.id == record_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()

    if not existing_record:
        raise HTTPException(status_code=404, detail="Record not found.")

    # PHASE 3 OBJECT-LEVEL OWNERSHIP CHECK
    await ownership_service.check_ownership(existing_record, current_user)

    if current_user.role != "Parish Priest":
        await process_modification_request(
            db=db,
            user=current_user,
            action_type="UPDATE",
            table_name="death_register",  # MUST match TABLE_MAP in approvals.py
            record_id=str(record_id),
            payload=payload.model_dump(mode='json')
        )
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
            "message": "Modification queued. Awaiting Parish Priest approval.",
            "canonical_reference": existing_record.formatted_number
        })

    # Direct Update for Parish Priests
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(existing_record, key, value)

    await db.commit()

    return {
        "message": "Record updated successfully.",
        "canonical_reference": existing_record.formatted_number
    }