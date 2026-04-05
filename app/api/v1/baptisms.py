from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
import uuid
from typing import Any, Dict

# Secure internal imports
from app.core.dependencies import (
    get_db,
    require_create_access,
    require_read_access,
    require_update_access,
    process_modification_request
)
from app.models.all_models import BaptismModel, GlobalRegistryIndex, User
from app.schemas.schemas import BaptismCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER BAPTISM (CANONICAL DATA ENTRY)
# ==============================================================================

@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_recent_baptisms(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    query = select(BaptismModel).order_by(desc(BaptismModel.date_of_baptism)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}

@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_baptism(
        baptism_in: BaptismCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_create_access)  # SECURITY: Must have create privileges
):
    """
    Creates a canonical baptism record.
    Generates a sequential tracking number and dual-writes to the Local Parish and Global Diocesan Index.
    """
    current_year = baptism_in.date_of_baptism.year

    # 1. Generate Sequential Canonical Number (e.g., 1/2026)
    # We query the database to find the highest row number used so far this specific year.
    query = await db.execute(
        select(func.max(BaptismModel.row_number)).where(BaptismModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        # 2. Prepare the Primary Baptism Record
        # We use Pydantic V2's .model_dump() to safely convert the validated schema into a dictionary.
        new_bap = BaptismModel(
            **baptism_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number
        )
        db.add(new_bap)
        await db.flush()  # Flush locks the row and generates the UUID without committing the transaction yet

        # 3. Global Diocesan Indexing
        # We copy key identifying data to the public index so the Chancery can search for parishioners diocese-wide.
        full_first_name = new_bap.first_name
        if new_bap.middle_name:
            full_first_name = f"{new_bap.first_name} {new_bap.middle_name}"

        global_entry = GlobalRegistryIndex(
            first_name=full_first_name,
            last_name=new_bap.last_name,
            canonical_number=canonical_number,
            baptism_number=canonical_number,
            record_type="BAPTISM",
            parish_id=_current_user.parish_id  # Identity mathematically guaranteed by the JWT
        )
        db.add(global_entry)

        # 4. Commit both records simultaneously (Atomic Transaction)
        await db.commit()

        return {
            "message": "Baptism registered successfully.",
            "canonical_reference": canonical_number,
            "id": str(new_bap.id)
        }

    except Exception as e:
        await db.rollback()  # If anything fails, revert the entire transaction to prevent corrupted partial data
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database Error: {str(e)}"
        )


# ==============================================================================
# 2. LOCAL SEARCH (TYPO-TOLERANT FUZZY SEARCH)
# ==============================================================================
@router.get("/search")
async def search_baptisms(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    """
    Performs an intelligent, fuzzy search within the baptismal registry.
    Handles spelling mistakes (e.g., finding "Mwaba" even if the user typed "Mwamba").
    """
    # Fetch all records to perform fuzzy matching in memory
    result = await db.execute(select(BaptismModel))
    rows = result.scalars().all()

    if not rows:
        return {"results": [], "message": "No records found."}

    search_strings = []
    record_map = []

    # Build the search index strings
    for record in rows:
        middle = record.middle_name if record.middle_name else ""
        search_data = f"{record.first_name} {middle} {record.last_name} {record.formatted_number}".lower()
        search_strings.append(search_data)
        record_map.append(record)

    # Use RapidFuzz to find the best matches with a minimum confidence score of 60%
    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)

    # Map the fuzzy match indexes back to the actual database objects
    results = [record_map[idx] for _, _, idx in matches]

    return {"query": q, "match_count": len(results), "results": results}


# ==============================================================================
# 3. UPDATE BAPTISM (GOVERNANCE WORKFLOW)
# ==============================================================================
@router.put("/{baptism_id}", status_code=status.HTTP_200_OK)
async def update_baptism(
        baptism_id: uuid.UUID,
        payload: BaptismCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)
):
    """
    Modifies an existing record.
    Strict Role-Based Access Control (RBAC) applied:
    - Assistant Priests/Secretaries: Queued for approval (Returns 202).
    - Parish Priests: Executes immediately (Returns 200).
    """
    # 1. Verify the target record actually exists
    query = select(BaptismModel).where(BaptismModel.id == baptism_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()

    if not existing_record:
        raise HTTPException(status_code=404, detail="Baptism record not found.")

    # 2. EXPLICIT SECURITY GATE: The Governance Queue
    # If the user is NOT a Parish Priest, they cannot modify the database directly.
    if current_user.role != "Parish Priest":
        # Save the proposed changes to the Pending Actions Queue as a JSON payload
        await process_modification_request(
            db=db,
            user=current_user,
            action_type="UPDATE",
            table_name="baptisms",
            record_id=str(baptism_id),
            payload=payload.model_dump(mode='json')  # mode='json' converts dates to strings for JSONB storage
        )

        # SECURITY FIX: Forcefully halt execution here and return a 202 Accepted.
        # This guarantees the code below this block is never reached by an Assistant Priest.
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Modification queued. Awaiting Parish Priest approval.",
                "canonical_reference": existing_record.formatted_number
            }
        )

    # 3. PARISH PRIEST EXECUTION (Direct Update)
    # The execution flow will ONLY reach this line if the user is a Parish Priest.
    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(existing_record, key, value)

    await db.commit()

    return {
        "message": "Baptism record updated successfully.",
        "canonical_reference": existing_record.formatted_number
    }