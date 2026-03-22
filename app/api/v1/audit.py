from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
from typing import Optional

# Security: Only high-level officials should be reading global audit logs
from app.core.dependencies import get_db, require_read_access
from app.models.all_models import AuditLogModel

router = APIRouter()


# ==============================================================================
# 1. VIEW DIOCESAN AUDIT LOGS (TAMPER-PROOF LEDGER)
# ==============================================================================
@router.get("/")
async def get_audit_logs(
        limit: int = Query(50, description="Number of records to return"),
        skip: int = Query(0, description="Pagination offset"),
        target_table: Optional[str] = Query(None, description="Filter by table (e.g., baptisms)"),
        action_type: Optional[str] = Query(None, description="Filter by action (e.g., UPDATE, DELETE)"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)  # Expand to require_admin based on your exact RBAC
):
    """
    Retrieves the chronological history of all approved edits and deletions
    made to canonical records.
    """

    # 1. Base Query: Ordered by most recent changes first
    query = select(AuditLogModel).order_by(desc(AuditLogModel.changed_at))

    # 2. Apply Dynamic Filters if requested
    if target_table:
        query = query.where(AuditLogModel.target_table == target_table)
    if action_type:
        query = query.where(AuditLogModel.action_type == action_type)

    # 3. Apply Pagination
    query = query.offset(skip).limit(limit)

    results = (await db.execute(query)).scalars().all()

    return {
        "message": "Audit ledger retrieved successfully.",
        "count": len(results),
        "logs": results
    }


# ==============================================================================
# 2. VIEW RECORD-SPECIFIC HISTORY
# ==============================================================================
@router.get("/record/{record_id}")
async def get_record_history(
        record_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    """
    Fetches the complete edit history for a single specific canonical record.
    (e.g., "Show me every time Elias Phiri's baptism was edited").
    """
    query = select(AuditLogModel).where(AuditLogModel.target_record_id == str(record_id)).order_by(
        desc(AuditLogModel.changed_at))
    results = (await db.execute(query)).scalars().all()

    if not results:
        return {"message": "No modification history found for this record. It is in its original canonical state.",
                "logs": []}

    return {"message": f"Found {len(results)} historical modifications.", "logs": results}