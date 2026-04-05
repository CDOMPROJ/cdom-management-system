from fastapi import APIRouter, Depends, status, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from rapidfuzz import process
import uuid
from typing import Any, Dict

from app.core.dependencies import get_db, require_create_access, require_read_access, require_update_access, process_modification_request
from app.models.all_models import GlobalRegistryIndex, User

class BaseCRUDRouter:
    """Refined common CRUD mixin extracted from all sacramental routers.
    Provides register, search, and update with approval queue logic."""

    def __init__(self, model, schema_create, record_type: str):
        self.model = model
        self.schema_create = schema_create
        self.record_type = record_type

    def get_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
        async def get_recent(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
            """Returns recent records with pagination."""
            query = select(self.model).order_by(desc(self.model.date_of_baptism if hasattr(self.model, 'date_of_baptism') else self.model.date_of_death if hasattr(self.model, 'date_of_death') else getattr(self.model, 'marriage_date', None))).offset(offset).limit(limit)
            result = await db.execute(query)
            records = result.scalars().all()
            return {"count": len(records), "results": records}

        @router.post("/", status_code=status.HTTP_201_CREATED)
        async def register(payload: self.schema_create, db: AsyncSession = Depends(get_db), _current_user: User = Depends(require_create_access)):
            """Creates a new canonical record with auto-generated number and global index entry."""
            current_year = getattr(payload, 'date_of_baptism', getattr(payload, 'date_of_death', getattr(payload, 'marriage_date', getattr(payload, 'confirmation_date', None)))).year
            query = await db.execute(select(func.max(self.model.row_number)).where(getattr(self.model, 'registry_year') == current_year))
            max_row = query.scalar() or 0
            new_row = max_row + 1
            canonical_number = f"{new_row}/{current_year}"

            try:
                new_record = self.model(**payload.model_dump(), row_number=new_row, registry_year=current_year, formatted_number=canonical_number)
                db.add(new_record)
                await db.flush()

                full_first_name = new_record.first_name
                if getattr(new_record, 'middle_name', None):
                    full_first_name = f"{new_record.first_name} {new_record.middle_name}"

                global_entry = GlobalRegistryIndex(first_name=full_first_name, last_name=new_record.last_name, canonical_number=canonical_number, baptism_number=getattr(new_record, 'baptism_number', canonical_number), record_type=self.record_type, parish_id=_current_user.parish_id)
                db.add(global_entry)
                await db.commit()

                return {"message": f"{self.record_type} registered successfully.", "canonical_reference": canonical_number, "id": str(new_record.id)}
            except Exception as e:
                await db.rollback()
                raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

        @router.get("/search")
        async def search(q: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db), _current_user: User = Depends(require_read_access)):
            """Fuzzy search using RapidFuzz for typo tolerance."""
            result = await db.execute(select(self.model))
            rows = result.scalars().all()
            if not rows:
                return {"results": [], "message": "No records found."}
            search_strings = []
            record_map = []
            for record in rows:
                middle = getattr(record, 'middle_name', '') or ''
                search_data = f"{record.first_name} {middle} {record.last_name} {getattr(record, 'formatted_number', '')}".lower()
                search_strings.append(search_data)
                record_map.append(record)
            matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)
            return {"query": q, "match_count": len(matches), "results": [record_map[idx] for _, _, idx in matches]}

        @router.put("/{record_id}", status_code=status.HTTP_200_OK)
        async def update(record_id: uuid.UUID, payload: self.schema_create, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_update_access)):
            """Updates record with Parish Priest approval queue for non-priests."""
            query = select(self.model).where(self.model.id == record_id)
            existing_record = (await db.execute(query)).scalar_one_or_none()
            if not existing_record:
                raise HTTPException(status_code=404, detail="Record not found.")
            if current_user.role != "Parish Priest":
                await process_modification_request(db=db, user=current_user, action_type="UPDATE", table_name=self.model.__tablename__, record_id=str(record_id), payload=payload.model_dump(mode='json'))
                return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"message": "Modification queued. Awaiting Parish Priest approval.", "canonical_reference": existing_record.formatted_number})
            for key, value in payload.model_dump(exclude_unset=True).items():
                setattr(existing_record, key, value)
            await db.commit()
            return {"message": "Record updated successfully.", "canonical_reference": existing_record.formatted_number}

        return router