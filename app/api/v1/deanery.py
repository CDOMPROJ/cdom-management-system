from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import DiocesanAnalyticsModel, ParishModel

router = APIRouter()

def verify_deanery_role(current_user: dict = Depends(get_current_active_user)):
    """Ensures only a Dean, Bishop, Vicar General, or SysAdmin can view this."""
    allowed_roles = ["Dean", "Bishop", "Vicar General", "SysAdmin"]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Deanery-level access required.")
    
    # If the user is a Dean, ensure they actually have a deanery assigned
    if current_user.get("role") == "Dean" and not current_user.get("deanery_id"):
        raise HTTPException(status_code=400, detail="Dean account is not linked to a Deanery.")
        
    return current_user

@router.get("/{deanery_id}/overview")
async def get_deanery_overview(
    deanery_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(verify_deanery_role)
):
    """Returns the aggregated totals for a specific Deanery."""
    
    # Security Check: A Dean can only view his OWN deanery. 
    # Bishops and SysAdmins bypass this check.
    if admin_user.get("role") == "Dean" and admin_user.get("deanery_id") != deanery_id:
        raise HTTPException(status_code=403, detail="You can only view analytics for your assigned Deanery.")

    # We join the Analytics table with the Parish table to filter by deanery_id
    query = await db.execute(
        select(
            func.sum(DiocesanAnalyticsModel.total_baptisms_ytd).label('total_baptisms'),
            func.sum(DiocesanAnalyticsModel.total_communions_ytd).label('total_communions'),
            func.sum(DiocesanAnalyticsModel.total_confirmations_ytd).label('total_confirmations'),
            func.sum(DiocesanAnalyticsModel.total_marriages_ytd).label('total_marriages'),
            func.sum(DiocesanAnalyticsModel.total_deaths_ytd).label('total_deaths'),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_target_ytd).label('total_target'),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_actual_ytd).label('total_actual')
        )
        .select_from(DiocesanAnalyticsModel)
        .join(ParishModel, DiocesanAnalyticsModel.parish_id == ParishModel.id)
        .where(ParishModel.deanery_id == deanery_id)
    )
    result = query.one()
    
    target = result.total_target or 0
    actual = result.total_actual or 0

    return {
        "deanery_sacramental_totals": {
            "baptisms": result.total_baptisms or 0,
            "first_communions": result.total_communions or 0,
            "confirmations": result.total_confirmations or 0,
            "marriages": result.total_marriages or 0,
            "deaths": result.total_deaths or 0,
        },
        "deanery_financial_health": {
            "total_cdom_target_zmw": target,
            "total_cdom_actual_zmw": actual,
            "variance_zmw": actual - target
        }
    }

@router.get("/{deanery_id}/parishes")
async def get_deanery_parishes(
    deanery_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(verify_deanery_role)
):
    """Returns the individual analytics rows for parishes strictly within this Deanery."""
    
    if admin_user.get("role") == "Dean" and admin_user.get("deanery_id") != deanery_id:
        raise HTTPException(status_code=403, detail="Unauthorized.")

    query = await db.execute(
        select(DiocesanAnalyticsModel)
        .join(ParishModel, DiocesanAnalyticsModel.parish_id == ParishModel.id)
        .where(ParishModel.deanery_id == deanery_id)
        .order_by(DiocesanAnalyticsModel.parish_name)
    )
    parishes = query.scalars().all()
    
    return {"parishes": parishes}