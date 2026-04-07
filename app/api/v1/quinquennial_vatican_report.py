from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any

# PHASE 3 SECURE IMPORTS (replacing old dependencies)
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker
from app.db.session import get_db
from app.models.all_models import User, GlobalRegistryIndex

router = APIRouter()


@router.get("/quinquennial-summary", response_model=Dict[str, Any])
async def get_global_vatican_report(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)  # PHASE 3: Full User object with ownership/ABAC
):
    """
    Aggregates all Sacraments across all parishes for the 5-Year Vatican Report.
    Operates at lightning speed by querying the unified Global Index.
    """
    # PHASE 3 ABAC ENFORCEMENT (Bishop-only)
    await PermissionChecker("bishop:report")(current_user)

    # 1. Base query against the Index
    base_query = select(GlobalRegistryIndex.record_type, func.count(GlobalRegistryIndex.id)).group_by(GlobalRegistryIndex.record_type)
    results = (await db.execute(base_query)).all()

    # 2. Map the results
    totals = {
        "baptisms": 0,
        "first_communions": 0,
        "confirmations": 0,
        "marriages": 0,
        "deaths": 0
    }

    for record_type, count in results:
        if record_type == "BAPTISM": totals["baptisms"] = count
        elif record_type == "FIRST_COMMUNION": totals["first_communions"] = count
        elif record_type == "CONFIRMATION": totals["confirmations"] = count
        elif record_type == "MARRIAGE": totals["marriages"] = count
        elif record_type == "DEATH": totals["deaths"] = count

    return {
        "report_type": "Quinquennial Diocesan Summary (Vatican Submission)",
        "scope": "All Parishes",
        "sacramental_totals": totals
    }