from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from rapidfuzz import process
import uuid

# Secure internal imports
from app.core.dependencies import (
    get_db, require_create_access, require_read_access,
    require_update_access, process_modification_request
)
from app.models.all_models import DeathRegisterModel, BaptismModel, GlobalRegistryIndex, User
from app.schemas.schemas import DeathRegisterCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER DEATH (WITH AUTOMATED BAPTISM LINKING)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_death(
        death_in: DeathRegisterCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_create_access)
):
    """
    Registers a death and creates a shadow entry in the Global CDOM Index.
    If a baptism_number is provided, it automatically marks the local Baptism record as deceased.
    """
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
            formatted_number=canonical_number
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
            parish_id=_current_user.parish_id
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
        _current_user: User = Depends(require_read_access)
):
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
        current_user: User = Depends(require_update_access)
):
    """
    Modifies a death record, protected by the Parish Priest Governance Queue.
    """
    query = select(DeathRegisterModel).where(DeathRegisterModel.id == record_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()

    if not existing_record:
        raise HTTPException(status_code=404, detail="Record not found.")

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