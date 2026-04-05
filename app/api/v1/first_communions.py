from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
from typing import Dict, Any
import uuid

# Secure internal imports
from app.core.dependencies import (
    get_db, require_create_access, require_read_access,
    require_update_access, process_modification_request
)
from app.models.all_models import FirstCommunionModel, GlobalRegistryIndex, User
from app.schemas.old_schemas import FirstCommunionCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER FIRST COMMUNION
# ==============================================================================
@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_recent_communions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    query = select(FirstCommunionModel).order_by(desc(FirstCommunionModel.communion_date)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}

@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_first_communion(
        communion_in: FirstCommunionCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_create_access)
):
    current_year = communion_in.communion_date.year

    query = await db.execute(
        select(func.max(FirstCommunionModel.row_number)).where(FirstCommunionModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        new_communion = FirstCommunionModel(
            **communion_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number
        )
        db.add(new_communion)
        await db.flush()

        # Global Diocesan Indexing
        full_first_name = new_communion.first_name
        if new_communion.middle_name:
            full_first_name = f"{new_communion.first_name} {new_communion.middle_name}"

        global_entry = GlobalRegistryIndex(
            first_name=full_first_name,
            last_name=new_communion.last_name,
            canonical_number=canonical_number,
            baptism_number=new_communion.baptism_number,
            record_type="FIRST_COMMUNION",
            parish_id=_current_user.parish_id
        )
        db.add(global_entry)
        await db.commit()

        return {"message": "First Communion registered successfully.", "canonical_reference": canonical_number,
                "id": str(new_communion.id)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# ==============================================================================
# 2. LOCAL SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/search")
async def search_communions(
        q: str = Query(..., min_length=2),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    result = await db.execute(select(FirstCommunionModel))
    rows = result.scalars().all()
    if not rows: return {"results": [], "message": "No records found."}

    search_strings, record_map = [], []
    for record in rows:
        middle = record.middle_name or ""
        search_data = f"{record.first_name} {middle} {record.last_name} {record.formatted_number} {record.baptism_number}".lower()
        search_strings.append(search_data)
        record_map.append(record)

    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)
    return {"query": q, "match_count": len(matches), "results": [record_map[idx] for _, _, idx in matches]}


# ==============================================================================
# 3. UPDATE FIRST COMMUNION (GOVERNANCE WORKFLOW)
# ==============================================================================
@router.put("/{record_id}", status_code=status.HTTP_200_OK)
async def update_first_communion(
        record_id: uuid.UUID,
        payload: FirstCommunionCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)
):
    query = select(FirstCommunionModel).where(FirstCommunionModel.id == record_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()

    if not existing_record: raise HTTPException(status_code=404, detail="Record not found.")

    if current_user.role != "Parish Priest":
        await process_modification_request(
            db=db, user=current_user, action_type="UPDATE", table_name="first_communions",
            record_id=str(record_id), payload=payload.model_dump(mode='json')
        )
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={
            "message": "Modification queued. Awaiting Parish Priest approval.",
            "canonical_reference": existing_record.formatted_number
        })

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(existing_record, key, value)
    await db.commit()

    return {"message": "Record updated successfully.", "canonical_reference": existing_record.formatted_number}