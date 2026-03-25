from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from datetime import date  # <--- ADDED: Required for JSON-to-Date parsing

# Security & Core
from app.core.dependencies import get_db, require_parish_priest
from app.models.all_models import (
    PendingActionModel,
    BaptismModel,
    ConfirmationModel,
    FirstCommunionModel,
    MarriageModel,
    DeathRegisterModel,
    AuditLogModel,
    User
)

router = APIRouter()

# ==============================================================================
# DYNAMIC TABLE MAPPING
# Maps the string name in the database to the actual SQLAlchemy Python Class
# ==============================================================================
TABLE_MAP = {
    "baptisms": BaptismModel,
    "confirmations": ConfirmationModel,
    "first_communions": FirstCommunionModel,
    "marriages": MarriageModel,
    "death_register": DeathRegisterModel
}


# ==============================================================================
# 1. VIEW PENDING ACTIONS (THE PRIEST'S INBOX)
# ==============================================================================
@router.get("/pending", status_code=status.HTTP_200_OK)
async def get_pending_actions(
        db: AsyncSession = Depends(get_db),
        _current_pp: User = Depends(require_parish_priest)  # SECURITY: Object-based access
):
    """Fetches all actions awaiting the Parish Priest's approval."""
    query = select(PendingActionModel).where(PendingActionModel.status == "PENDING").order_by(
        PendingActionModel.created_at.desc())
    results = (await db.execute(query)).scalars().all()

    return {
        "message": f"You have {len(results)} pending actions requiring review.",
        "queue": results
    }


# ==============================================================================
# 2. APPROVE ACTION (WITH COMPREHENSIVE AUDIT LOGGING)
# ==============================================================================
@router.post("/{action_id}/approve", status_code=status.HTTP_200_OK)
async def approve_action(
        action_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_pp: User = Depends(require_parish_priest)
):
    """Approves an edit, applies the payload, and permanently writes to the Audit Ledger."""

    # 1. Fetch the Pending Action
    action_query = await db.execute(select(PendingActionModel).where(PendingActionModel.id == action_id))
    action = action_query.scalar_one_or_none()

    if not action or action.status != "PENDING":
        raise HTTPException(status_code=404, detail="Action not found or already processed.")

    # 2. Identify the target SQLAlchemy Model
    TargetModel = TABLE_MAP.get(action.target_table)
    if not TargetModel:
        raise HTTPException(status_code=500, detail=f"System Error: Unmapped target table '{action.target_table}'")

    # 3. Fetch the actual canonical record being edited
    try:
        record_uuid = uuid.UUID(action.target_record_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target record ID format.")

    record_query = await db.execute(select(TargetModel).where(TargetModel.id == record_uuid))
    target_record = record_query.scalar_one_or_none()

    if not target_record:
        raise HTTPException(status_code=404, detail="The canonical record could not be found.")

    # 4. CAPTURE THE "BEFORE" STATE FOR THE AUDIT LOG
    old_values = {}
    for key in action.proposed_payload.keys():
        if hasattr(target_record, key):
            old_value = getattr(target_record, key)
            # Convert dates to strings for JSON serialization
            if hasattr(old_value, "isoformat"):
                old_value = old_value.isoformat()
            old_values[key] = str(old_value) if old_value is not None else None  # Safe stringification

    # 5. Dynamically apply the new JSON payload to the Canonical Record
    for key, value in action.proposed_payload.items():
        if hasattr(target_record, key):

            # THE FIX: If the value is a string that looks like a date (YYYY-MM-DD),
            # safely convert it back to a Python date object so PostgreSQL accepts it.
            if isinstance(value, str) and len(value) == 10 and value.count("-") == 2:
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    pass  # If it fails to parse, just leave it as a string

            setattr(target_record, key, value)

    # 6. WRITE TO THE AUDIT LEDGER
    audit_entry = AuditLogModel(
        action_type=action.action_type,
        target_table=action.target_table,
        target_record_id=str(target_record.id),
        changed_by_email=current_pp.email,  # Type-safe object access
        old_values=old_values,
        new_values=action.proposed_payload
    )
    db.add(audit_entry)

    # 7. Update the Action Status
    action.status = "APPROVED"

    await db.commit()

    return {
        "message": "Action approved, record updated, and audit log securely written.",
        "record_id": action.target_record_id
    }


# ==============================================================================
# 3. REJECT ACTION
# ==============================================================================
@router.post("/{action_id}/reject", status_code=status.HTTP_200_OK)
async def reject_action(
        action_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        _current_pp: User = Depends(require_parish_priest)
):
    """Rejects an edit. The canonical record remains untouched."""
    action_query = await db.execute(select(PendingActionModel).where(PendingActionModel.id == action_id))
    action = action_query.scalar_one_or_none()

    if not action or action.status != "PENDING":
        raise HTTPException(status_code=404, detail="Action not found or already processed.")

    action.status = "REJECTED"

    await db.commit()
    return {"message": "Action has been rejected and archived."}