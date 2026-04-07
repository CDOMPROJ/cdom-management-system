# ==============================================================================
# app/api/v1/marriage.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
from typing import Any, Dict
import uuid

from app.core.dependencies import process_modification_request
# PHASE 3 SECURE IMPORTS (consolidated – no old dependencies folder)
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import MarriageModel, User
from app.schemas.schemas import MarriageCreate

router = APIRouter()

# Phase 3 Ownership Service
ownership_service = OwnershipService()


# ==============================================================================
# 1. REGISTER MARRIAGE (CANONICAL DATA ENTRY)
# ==============================================================================
@router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_recent_marriages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("parish:read")(current_user)

    query = select(MarriageModel).order_by(desc(MarriageModel.marriage_date)).offset(offset).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"count": len(records), "results": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_marriage(
        marriage_in: MarriageCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Creates a canonical marriage record linking the Groom and Bride.
    Automatically generates a sequential tracking number for the current year.
    """
    # PHASE 3 ABAC + OWNERSHIP ENFORCEMENT
    await PermissionChecker("parish:write")(current_user)
    await ownership_service.check_ownership(marriage_in, current_user)

    current_year = marriage_in.marriage_date.year

    # 1. Generate Sequential Canonical Number (e.g., 1/2026)
    # Queries the database for the highest row number used this specific year for marriages.
    query = await db.execute(
        select(func.max(MarriageModel.row_number)).where(MarriageModel.registry_year == current_year)
    )
    max_row = query.scalar() or 0
    new_row = max_row + 1
    canonical_number = f"{new_row}/{current_year}"

    try:
        # 2. Prepare the Primary Marriage Record
        # Uses Pydantic V2's .model_dump() to safely convert the validated schema
        new_marriage = MarriageModel(
            **marriage_in.model_dump(),
            row_number=new_row,
            registry_year=current_year,
            formatted_number=canonical_number,
            # PHASE 3 OWNERSHIP COLUMNS (added – old logic untouched)
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )

        db.add(new_marriage)
        await db.commit()
        await db.refresh(new_marriage)

        return {
            "message": "Holy Matrimony registered successfully.",
            "canonical_reference": canonical_number,
            "id": str(new_marriage.id)
        }

    except Exception as e:
        await db.rollback()  # Prevent corrupted partial data
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database Error: {str(e)}"
        )


# ==============================================================================
# 2. LOCAL SEARCH (DUAL-PARTY FUZZY SEARCH)
# ==============================================================================
@router.get("/search")
async def search_marriages(
        q: str = Query(..., min_length=2, description="Search by Groom, Bride, or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Performs an intelligent, fuzzy search within the marriage registry.
    Uniquely concatenates both the Groom's and Bride's details so either can be searched.
    """
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("parish:read")(current_user)

    # Fetch all records to perform fuzzy matching in memory
    result = await db.execute(select(MarriageModel))
    rows = result.scalars().all()

    if not rows:
        return {"results": [], "message": "No marriage records found."}

    search_strings = []
    record_map = []

    # Build the dual-party search index strings
    for record in rows:
        # We assume the model has groom and bride name fields based on standard canonical forms
        groom_name = f"{record.groom_first_name} {record.groom_last_name}"
        bride_name = f"{record.bride_first_name} {record.bride_last_name}"

        search_data = f"{groom_name} {bride_name} {record.formatted_number}".lower()
        search_strings.append(search_data)
        record_map.append(record)

    # Use RapidFuzz to find the best matches with a minimum confidence score of 60%
    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)

    # Map the fuzzy match indexes back to the actual database objects
    results = [record_map[idx] for _, _, idx in matches]

    return {"query": q, "match_count": len(results), "results": results}


# ==============================================================================
# 3. UPDATE MARRIAGE (ZERO-TRUST GOVERNANCE WORKFLOW)
# ==============================================================================
@router.put("/{marriage_id}", status_code=status.HTTP_200_OK)
async def update_marriage(
        marriage_id: uuid.UUID,
        payload: MarriageCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Modifies an existing marriage record.
    Strict Role-Based Access Control (RBAC) applied:
    - Assistant Priests: Queued for approval (Returns 202).
    - Parish Priests: Executes immediately (Returns 200).
    """
    # PHASE 3 ABAC + OWNERSHIP ENFORCEMENT
    await PermissionChecker("parish:write")(current_user)

    # 1. Verify the target record exists
    query = select(MarriageModel).where(MarriageModel.id == marriage_id)
    existing_record = (await db.execute(query)).scalar_one_or_none()

    if not existing_record:
        raise HTTPException(status_code=404, detail="Marriage record not found.")

    # PHASE 3 OBJECT-LEVEL OWNERSHIP CHECK
    await ownership_service.check_ownership(existing_record, current_user)

    # 2. EXPLICIT SECURITY GATE: The Governance Queue
    if current_user.role != "Parish Priest":
        # Save the proposed changes to the Pending Actions Queue
        await process_modification_request(
            db=db,
            user=current_user,
            action_type="UPDATE",
            table_name="marriages",  # This MUST match the string in approvals.py TABLE_MAP
            record_id=str(marriage_id),
            payload=payload.model_dump(mode='json')  # mode='json' serializes dates perfectly
        )

        # Forcefully halt execution and return a 202 Accepted.
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Marriage modification queued. Awaiting Parish Priest approval.",
                "canonical_reference": existing_record.formatted_number
            }
        )

    # 3. PARISH PRIEST EXECUTION (Direct Update)
    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(existing_record, key, value)

    await db.commit()

    return {
        "message": "Marriage record updated successfully.",
        "canonical_reference": existing_record.formatted_number
    }