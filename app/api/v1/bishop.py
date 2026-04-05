from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.dependencies import get_db, require_bishop_access
from app.models.all_models import User, DiocesanAnalyticsModel, GlobalRegistryIndex, ClergyRegistryModel
from app.ml.vocation_forecaster import generate_intelligence_horizon

router = APIRouter()

@router.get("/intelligence-horizon", response_model=Dict[str, Any])
async def get_intelligence_horizon(
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)
):
    """
    REVISED BISHOP-ONLY INTELLIGENCE HORIZON DASHBOARD CARD
    Combines registry status, ML predictions, and aggregates.
    Forecast visualization is now clean, chart-ready with yearly data,
    predicted values, confidence bands, growth rates, and trend direction.
    """
    now = datetime.now(timezone.utc)

    # Registry Status Summary
    registry_query = await db.execute(
        select(
            ClergyRegistryModel.category,
            ClergyRegistryModel.status,
            func.count(ClergyRegistryModel.id).label("count")
        )
        .group_by(ClergyRegistryModel.category, ClergyRegistryModel.status)
    )
    registry_data = registry_query.all()

    registry_summary = {}
    for category, status, count in registry_data:
        if category not in registry_summary:
            registry_summary[category] = {}
        registry_summary[category][status] = int(count)

    # ML Predictions with Revised Forecast Visualization
    ml_horizon = await generate_intelligence_horizon(db)

    # Diocesan Aggregates
    aggregates_query = await db.execute(
        select(
            func.sum(DiocesanAnalyticsModel.total_baptisms_ytd).label("total_baptisms"),
            func.sum(DiocesanAnalyticsModel.total_marriages_ytd).label("total_marriages")
        )
    )
    aggregates = aggregates_query.one_or_none() or (0, 0)

    return {
        "card_title": "Intelligence Horizon – Bishop Only",
        "last_updated": now.isoformat(),
        "overview": {
            "total_active_clergy": sum(v.get("Active", 0) for v in registry_summary.values()),
            "total_parishes_covered": len(registry_summary.get("Diocesan Priest", {})) + len(registry_summary.get("Religious Priest", {}))
        },
        "registry_summary": registry_summary,
        "risk_assessment": ml_horizon.get("risk_parishes", []),
        "five_year_forecast": ml_horizon.get("five_year_forecast", []),
        "diocesan_aggregates": {
            "total_baptisms_ytd": int(aggregates[0] or 0),
            "total_marriages_ytd": int(aggregates[1] or 0)
        },
        "actionable_insights": ml_horizon.get("recommended_actions", [
            "Prioritize reinforcement in high-risk parishes",
            "Monitor declining baptism trends in affected congregations"
        ])
    }