from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from rapidfuzz import process

from app.core.dependencies import get_db, get_current_user
from app.models.all_models import GlobalRegistryIndex, ParishModel
from app.schemas.schemas import SearchResponse, GlobalSearchResult

router = APIRouter()


# ==============================================================================
# PHASE 3: INTELLIGENT GLOBAL SEARCH (TYPO-TOLERANT)
# ==============================================================================
@router.get("/", response_model=SearchResponse)
async def global_search(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_user)
):
    """
    Queries the public Global Registry Index using RapidFuzz for typo-tolerance.
    Deans and Bishops can find records even if the Secretary misspelled them.
    """

    # 1. Fetch the Index
    query = select(GlobalRegistryIndex, ParishModel.name.label("parish_name")).join(
        ParishModel, GlobalRegistryIndex.parish_id == ParishModel.id
    )
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return SearchResponse(scope="GLOBAL", message="The Global Index is currently empty.", results=[])

    # 2. Prepare Parallel Lists for 100% Type Safety
    search_strings: list[str] = []
    record_map: list[tuple] = []

    for index_record, parish_name in rows:
        # Build the searchable string
        search_str = f"{index_record.first_name} {index_record.last_name} {index_record.canonical_number}".lower()

        # Append to our parallel lists
        search_strings.append(search_str)
        record_map.append((index_record, parish_name))

    # 3. Execute the Fuzzy Search
    # PyCharm perfectly understands list[str]. RapidFuzz uses WRatio by default.
    fuzzy_results = process.extract(
        q.lower(),
        search_strings,
        limit=50,
        score_cutoff=65.0
    )

    # 4. Format the matched results for the frontend
    formatted_results = []

    # RapidFuzz returns (matched_string, score, index_in_list)
    for match_string, score, match_index in fuzzy_results:
        # Use the integer index to grab the original database objects
        index_record, parish_name = record_map[match_index]

        formatted_results.append(
            GlobalSearchResult(
                name=f"{index_record.first_name} {index_record.last_name}",
                canonical=index_record.canonical_number,
                parish=parish_name,
                type=index_record.record_type
            )
        )

    return SearchResponse(
        scope="GLOBAL",
        message=f"Found {len(formatted_results)} intelligent matches for '{q}'.",
        results=formatted_results
    )