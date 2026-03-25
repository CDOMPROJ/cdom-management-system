from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
from typing import Optional

from app.core.dependencies import get_db, require_read_access
from app.models.all_models import AuditLogModel, User

router = APIRouter()

@router.get("/")
async def get_audit_logs(
        limit: int = Query(50),
        skip: int = Query(0),
        target_table: Optional[str] = Query(None),
        action_type: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access) # FIXED: Now uses User object
):
    """Retrieves the chronological history of all approved edits to canonical records."""
    query = select(AuditLogModel).order_by(desc(AuditLogModel.changed_at))

    if target_table:
        query = query.where(AuditLogModel.target_table == target_table)
    if action_type:
        query = query.where(AuditLogModel.action_type == action_type)

    query = query.offset(skip).limit(limit)
    results = (await db.execute(query)).scalars().all()

    return {"message": "Audit ledger retrieved successfully.", "count": len(results), "logs": results}


@router.get("/record/{record_id}")
async def get_record_history(
        record_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    """Fetches the complete edit history for a single specific canonical record."""
    query = select(AuditLogModel).where(AuditLogModel.target_record_id == str(record_id)).order_by(desc(AuditLogModel.changed_at))
    results = (await db.execute(query)).scalars().all()

    if not results:
        return {"message": "No modification history found for this record.", "logs": []}
    return {"logs": results}