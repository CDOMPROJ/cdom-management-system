from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from rapidfuzz import process

from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import BaptismModel, GlobalRegistryIndex
from app.schemas.schemas import BaptismCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER BAPTISM (ZERO TRUST ARCHITECTURE)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_baptism(
        baptism_in: BaptismCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_create_access)
):
    """
    Creates the canonical baptism record.
    SECURITY: The Parish identity is cryptographically derived from the _current_user
    token. Any attempts by the client to forge a parish name are ignored.
    """
    current_year = baptism_in.date_of_baptism.year

    # Generate Sequential Canonical Number (e.g., 125/2026)
    query = await db.execute(
        select(func.max(BaptismModel.row_number)).where(BaptismModel.registry_year == current_year)
    )
    new_row = (query.scalar() or 0) + 1
    canonical_number = f"{new_row}/{current_year}"

    # 1. Save to the Local Tenant Schema (Parish level)
    new_bap = BaptismModel(
        **baptism_in.model_dump(),
        row_number=new_row,
        registry_year=current_year,
        formatted_number=canonical_number
    )
    db.add(new_bap)
    await db.flush()  # Flush to lock the transaction locally

    # 2. Switch to Public Schema for Global Diocesan Indexing
    await db.execute(text('SET search_path TO public'))

    # Build the display name (including the new middle_name if it exists)
    first_name_display = new_bap.first_name
    if new_bap.middle_name:
        first_name_display = f"{new_bap.first_name} {new_bap.middle_name}"

    global_entry = GlobalRegistryIndex(
        first_name=first_name_display,
        last_name=new_bap.last_name,
        canonical_number=canonical_number,
        baptism_number=canonical_number,
        record_type="BAPTISM",
        parish_id=_current_user["parish_id"]  # Forced by the backend token
    )
    db.add(global_entry)
    await db.commit()

    # 3. Securely revert the search path back to the tenant
    await db.execute(text(f'SET search_path TO "{_current_user["tenant_schema"]}", public'))

    return {
        "message": "Baptism registered successfully.",
        "canonical_reference": canonical_number
    }


# ==============================================================================
# 2. LOCAL TENANT SEARCH (TYPO-TOLERANT WITH MIDDLE NAMES)
# ==============================================================================
@router.get("/search")
async def search_baptisms(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    query = select(BaptismModel)
    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return {"scope": "NONE", "message": "No baptism records found in this parish.", "results": []}

    search_strings: list[str] = []
    record_map: list[BaptismModel] = []

    for record in rows:
        # Include the new middle_name in the fuzzy search algorithm
        middle = record.middle_name if record.middle_name else ""
        search_str = f"{record.first_name} {middle} {record.last_name} {record.formatted_number} {record.mother_first_name} {record.father_first_name}".lower()
        search_strings.append(search_str)
        record_map.append(record)

    fuzzy_results = process.extract(q.lower(), search_strings, limit=20, score_cutoff=65.0)
    formatted_results = [record_map[match_index] for _, _, match_index in fuzzy_results]

    return {
        "scope": "LOCAL",
        "message": f"Found {len(formatted_results)} intelligent matches for '{q}'.",
        "results": formatted_results
    }