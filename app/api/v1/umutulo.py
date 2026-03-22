from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime
from typing import List

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import DiocesanContributionModel, ParishModel
from app.schemas.schemas import DiocesanContributionCreate

router = APIRouter()

# ==========================================
# 1. LOG DIOCESAN CONTRIBUTION (UMUTULO)
# ==========================================
@router.post("/contributions", status_code=status.HTTP_201_CREATED)
async def log_umutulo_contribution(
        contribution_in: DiocesanContributionCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """
    Logs a contribution toward a mandatory CDOM fund (e.g. Seminarian Fund).
    Calculates variance (Actual vs Target) automatically for Bishop's analytics.
    """
    if not _current_user.get("parish_id"):
        raise HTTPException(status_code=403, detail="Only Parish accounts can log CDOM obligations.")

    # A. TENANT ROUTING: Ensure record is saved in the correct parish database schema
    parish_query = await db.execute(
        select(ParishModel.schema_name).where(ParishModel.id == _current_user["parish_id"])
    )
    schema_name = parish_query.scalar_one_or_none()
    await db.execute(text(f'SET search_path TO "{schema_name}"'))

    # B. ANALYTICS PREP: Define reporting year and sequential row number
    current_year = datetime.utcnow().year
    row_query = await db.execute(
        select(func.max(DiocesanContributionModel.row_number))
        .where(DiocesanContributionModel.reporting_year == current_year)
    )
    next_row = (row_query.scalar() or 0) + 1

    # C. VARIANCE LOGIC: If a target was set by the Diocese, calculate the deficit or surplus
    # Example: If target is 1000 and actual is 800, variance is -200.
    calculated_variance = None
    if contribution_in.target_amount is not None:
        calculated_variance = contribution_in.actual_amount - contribution_in.target_amount

    # D. SAVE: Persist the contribution record
    new_contribution = DiocesanContributionModel(
        row_number=next_row,
        reporting_year=current_year,
        fund_name=contribution_in.fund_name,
        target_amount=contribution_in.target_amount,
        actual_amount=contribution_in.actual_amount,
        variance_amount=calculated_variance,
        notes=contribution_in.notes
    )

    db.add(new_contribution)
    await db.commit()
    await db.refresh(new_contribution)

    return {
        "message": f"CDOM Obligation for '{new_contribution.fund_name}' recorded successfully.",
        "variance": new_contribution.variance_amount,
        "id": new_contribution.id
    }