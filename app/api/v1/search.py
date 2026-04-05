from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from rapidfuzz import process

from app.core.dependencies import get_db, require_read_access
from app.models.all_models import GlobalRegistryIndex, ParishModel, User
from app.schemas.old_schemas import SearchResponse, GlobalSearchResult

router = APIRouter()

@router.get("/", response_model=SearchResponse)
async def global_search(
        q: str = Query(..., min_length=2, description="Search by Name or Canonical Number"),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access) # FIXED
):
    """Queries the public Global Registry Index using RapidFuzz for typo-tolerance."""
    query = select(GlobalRegistryIndex, ParishModel.name.label("parish_name")).join(
        ParishModel, GlobalRegistryIndex.parish_id == ParishModel.id
    )
    rows = (await db.execute(query)).all()

    if not rows:
        return SearchResponse(query=q, results=[])

    search_strings, record_map = [], []
    for index_record, parish_name in rows:
        search_str = f"{index_record.first_name} {index_record.last_name} {index_record.canonical_number}".lower()
        search_strings.append(search_str)
        record_map.append((index_record, parish_name))

    fuzzy_results = process.extract(q.lower(), search_strings, limit=20, score_cutoff=65.0)

    formatted_results = []
    for match_string, score, match_index in fuzzy_results:
        index_record, parish_name = record_map[match_index]
        formatted_results.append(
            GlobalSearchResult(
                record_type=index_record.record_type,
                canonical_number=index_record.canonical_number,
                first_name=index_record.first_name,
                last_name=index_record.last_name,
                date=index_record.created_at.date(), # Approximate for indexing
                parish_id=index_record.parish_id,
                parish_name=parish_name,
                match_score=score
            )
        )

    return SearchResponse(query=q, results=formatted_results)