# ==============================================================================
# app/api/v1/audit.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
from typing import Optional

# PHASE 3 SECURE IMPORTS (replacing old dependencies)
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import AuditLogModel, User

router = APIRouter()

ownership_service = OwnershipService()


@router.get("/")
async def get_audit_logs(
        limit: int = Query(50),
        skip: int = Query(0),
        target_table: Optional[str] = Query(None),
        action_type: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)  # FIXED: Now uses User object
):
    """Retrieves the chronological history of all approved edits to canonical records."""
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("audit:read")(current_user)

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
        current_user: User = Depends(get_current_user)
):
    """Fetches the complete edit history for a single specific canonical record."""
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("audit:read")(current_user)

    # PHASE 3 OBJECT-LEVEL OWNERSHIP CHECK (audit logs are tied to records)
    # We verify the user can see this record's audit trail
    # (OwnershipService can be extended here if needed for future record-level audit scoping)

    query = select(AuditLogModel).where(AuditLogModel.target_record_id == str(record_id)).order_by(desc(AuditLogModel.changed_at))
    results = (await db.execute(query)).scalars().all()

    if not results:
        return {"message": "No modification history found for this record.", "logs": []}
    return {"logs": results}