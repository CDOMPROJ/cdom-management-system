from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from rapidfuzz import process

from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import BaptismModel, GlobalRegistryIndex, ParishModel
from app.schemas.schemas import BaptismCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER BAPTISM
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_baptism(
        baptism_in: BaptismCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_create_access)
):
    """Creates the canonical baptism record and a public Shadow Entry for global searching."""
    current_year = baptism_in.date_of_baptism.year
    query = await db.execute(
        select(func.max(BaptismModel.row_number)).where(BaptismModel.registry_year == current_year))
    new_row = (query.scalar() or 0) + 1
    canonical_number = f"{new_row}/{current_year}"

    # Save to local parish schema
    new_bap = BaptismModel(**baptism_in.model_dump(), row_number=new_row, registry_year=current_year,
                           formatted_number=canonical_number)
    db.add(new_bap)

    # Save a lightweight shadow record to the public schema
    global_entry = GlobalRegistryIndex(
        first_name=new_bap.first_name,
        last_name=new_bap.last_name,
        canonical_number=canonical_number,
        baptism_number=canonical_number,  # Redundant here, but consistent for searches
        record_type="BAPTISM",
        parish_id=_current_user["parish_id"]
    )
    db.add(global_entry)
    await db.commit()

    return {"message": "Baptism registered successfully.", "canonical_reference": canonical_number}


# ==============================================================================
# 2. LOCAL TENANT SEARCH (TYPO-TOLERANT)
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
        search_str = f"{record.first_name} {record.last_name} {record.formatted_number} {record.mother_first_name} {record.father_first_name}".lower()
        search_strings.append(search_str)
        record_map.append(record)

    fuzzy_results = process.extract(q.lower(), search_strings, limit=20, score_cutoff=65.0)

    formatted_results = [record_map[match_index] for _, _, match_index in fuzzy_results]

    return {
        "scope": "LOCAL",
        "message": f"Found {len(formatted_results)} intelligent matches for '{q}'.",
        "results": formatted_results
    }
