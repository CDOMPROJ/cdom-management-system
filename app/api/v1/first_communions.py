from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from rapidfuzz import process

from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import FirstCommunionModel, GlobalRegistryIndex, ParishModel
from app.schemas.schemas import FirstCommunionCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER FIRST COMMUNION (WITH GLOBAL INDEXING)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_first_communion(
        communion_in: FirstCommunionCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_create_access)
):
    """
    Creates the canonical First Communion record in the Parish schema and creates
    a shadow entry in the Global CDOM Index.
    """
    current_year = communion_in.communion_date.year

    # 1. Generate Canonical Number
    query = await db.execute(
        select(func.max(FirstCommunionModel.row_number)).where(FirstCommunionModel.registry_year == current_year)
    )
    new_row = (query.scalar() or 0) + 1
    canonical_number = f"{new_row}/{current_year}"

    # 2. Save to local parish schema
    new_communion = FirstCommunionModel(
        **communion_in.model_dump(),
        row_number=new_row,
        registry_year=current_year,
        formatted_number=canonical_number
    )
    db.add(new_communion)
    await db.flush()  # Flush to get the ID

    # 3. Switch to Public Schema for Global Indexing
    await db.execute(text('SET search_path TO public'))

    # 4. Create Global Index Entry
    global_entry = GlobalRegistryIndex(
        first_name=new_communion.first_name,
        last_name=new_communion.last_name,
        canonical_number=canonical_number,
        baptism_number=new_communion.baptism_number,  # Extra link for cross-referencing
        record_type="FIRST_COMMUNION",
        parish_id=_current_user["parish_id"]
    )

    db.add(global_entry)
    await db.commit()

    # 5. Securely reset context back to the private schema
    await db.execute(text(f'SET search_path TO "{_current_user["tenant_schema"]}", public'))

    return {
        "message": "First Communion registered successfully.",
        "canonical_reference": canonical_number
    }


# ==============================================================================
# 2. LOCAL TENANT SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/search")
async def search_first_communions(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    query = select(FirstCommunionModel)
    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return {"scope": "NONE", "message": "No first communion records found in this parish.", "results": []}

    search_strings: list[str] = []
    record_map: list[FirstCommunionModel] = []

    for record in rows:
        search_str = f"{record.first_name} {record.last_name} {record.formatted_number} {record.baptism_number}".lower()
        search_strings.append(search_str)
        record_map.append(record)

    fuzzy_results = process.extract(q.lower(), search_strings, limit=20, score_cutoff=65.0)

    formatted_results = [record_map[match_index] for _, _, match_index in fuzzy_results]

    return {
        "scope": "LOCAL",
        "message": f"Found {len(formatted_results)} intelligent matches for '{q}'.",
        "results": formatted_results
    }