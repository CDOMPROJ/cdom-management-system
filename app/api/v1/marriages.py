from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from rapidfuzz import process

from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import MarriageModel, GlobalRegistryIndex
from app.schemas.schemas import MarriageCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER MARRIAGE (DOUBLE-ENTRY GLOBAL INDEXING)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_marriage(
        marriage_in: MarriageCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_create_access)
):
    """
    Creates the canonical marriage record. Generates TWO shadow entries
    (one for the Groom, one for the Bride) in the Global CDOM Index.
    """
    # Fixed: Schema uses date_of_marriage
    current_year = marriage_in.date_of_marriage.year

    # 1. Generate Canonical Number
    query = await db.execute(
        select(func.max(MarriageModel.row_number)).where(MarriageModel.registry_year == current_year)
    )
    new_row = (query.scalar() or 0) + 1
    canonical_number = f"{new_row}/{current_year}"

    # 2. Save to local parish schema
    new_marriage = MarriageModel(
        **marriage_in.model_dump(),
        row_number=new_row,
        registry_year=current_year,
        formatted_number=canonical_number,
        marriage_date=marriage_in.date_of_marriage  # Map the base schema field to DB column
    )
    db.add(new_marriage)
    await db.flush()

    # 3. Switch to Public Schema for Global Indexing
    await db.execute(text('SET search_path TO public'))

    # 4. The "Double Entry" Logic (Groom and Bride indexed separately)
    groom_entry = GlobalRegistryIndex(
        first_name=new_marriage.groom_first_name,
        last_name=new_marriage.groom_last_name,
        canonical_number=canonical_number,
        record_type="MARRIAGE",
        parish_id=_current_user["parish_id"]
    )

    bride_entry = GlobalRegistryIndex(
        first_name=new_marriage.bride_first_name,
        last_name=new_marriage.bride_last_name,
        canonical_number=canonical_number,
        record_type="MARRIAGE",
        parish_id=_current_user["parish_id"]
    )

    db.add_all([groom_entry, bride_entry])
    await db.commit()

    # 5. Securely reset context back to the private schema
    await db.execute(text(f'SET search_path TO "{_current_user["tenant_schema"]}", public'))

    return {
        "message": "Marriage registered successfully.",
        "canonical_reference": canonical_number
    }


# ==============================================================================
# 2. LOCAL TENANT SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/search")
async def search_marriages(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    query = select(MarriageModel)
    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return {"scope": "NONE", "message": "No marriage records found in this parish.", "results": []}

    search_strings: list[str] = []
    record_map: list[MarriageModel] = []

    for record in rows:
        groom_middle = record.groom_middle_name if record.groom_middle_name else ""
        bride_middle = record.bride_middle_name if record.bride_middle_name else ""

        search_str = f"{record.groom_first_name} {groom_middle} {record.groom_last_name} {record.bride_first_name} {bride_middle} {record.bride_last_name} {record.formatted_number}".lower()
        search_strings.append(search_str)
        record_map.append(record)

    fuzzy_results = process.extract(q.lower(), search_strings, limit=20, score_cutoff=65.0)
    formatted_results = [record_map[match_index] for _, _, match_index in fuzzy_results]

    return {
        "scope": "LOCAL",
        "message": f"Found {len(formatted_results)} intelligent matches for '{q}'.",
        "results": formatted_results
    }