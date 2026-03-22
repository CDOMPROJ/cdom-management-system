from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import DeathRegisterModel, BaptismModel, GlobalRegistryIndex
from app.schemas.schemas import DeathRegisterCreate

router = APIRouter()


# ==============================================================================
# 1. REGISTER DEATH (WITH BAPTISM TRIGGER & GLOBAL INDEXING)
# ==============================================================================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_death(
        death_in: DeathRegisterCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_create_access)
):
    """
    Registers a death, triggers an update to the local Baptism record (if applicable),
    and creates a shadow entry in the Global CDOM Index.
    """
    current_year = death_in.date_of_death.year

    # 1. Generate Canonical Number
    query = await db.execute(
        select(func.max(DeathRegisterModel.row_number)).where(DeathRegisterModel.registry_year == current_year)
    )
    new_row = (query.scalar() or 0) + 1
    canonical_number = f"{new_row}/{current_year}"

    # 2. Save Death to local parish schema
    new_death = DeathRegisterModel(
        **death_in.model_dump(),
        row_number=new_row,
        registry_year=current_year,
        formatted_number=canonical_number
    )
    db.add(new_death)
    await db.flush()  # Flush to secure the ID for the trigger

    # 3. THE TRIGGER: Update Baptism Record if it exists locally
    if death_in.baptism_number:
        baptism_query = await db.execute(
            select(BaptismModel).where(BaptismModel.formatted_number == death_in.baptism_number)
        )
        local_baptism = baptism_query.scalar_one_or_none()

        if local_baptism:
            local_baptism.is_deceased = True
            local_baptism.death_record_id = new_death.id
            # We don't need to db.add() because local_baptism is already tracked by the session

    # 4. Switch to Public Schema for Global Indexing
    await db.execute(text('SET search_path TO public'))

    # 5. Create Global Index Entry
    global_entry = GlobalRegistryIndex(
        first_name=new_death.first_name,
        last_name=new_death.last_name,
        canonical_number=canonical_number,
        baptism_number=new_death.baptism_number,
        record_type="DEATH",
        parish_id=_current_user["parish_id"]
    )

    db.add(global_entry)
    await db.commit()

    # 6. Securely reset context back to the private schema
    await db.execute(text(f'SET search_path TO "{_current_user["tenant_schema"]}", public'))

    return {
        "message": "Death registered successfully. Local baptism records updated if applicable.",
        "canonical_reference": canonical_number
    }


# ==============================================================================
# 2. LOCAL TENANT SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/search")
async def search_deaths(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    from rapidfuzz import process

    query = select(DeathRegisterModel)
    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return {"scope": "NONE", "message": "No death records found in this parish.", "results": []}

    search_strings: list[str] = []
    record_map: list[DeathRegisterModel] = []

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