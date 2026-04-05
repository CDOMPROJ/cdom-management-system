import numpy as np
from sklearn.ensemble import RandomForestClassifier
from prophet import Prophet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.all_models import GlobalRegistryIndex, ClergyRegistryModel, DiocesanAnalyticsModel

async def generate_intelligence_horizon(db: AsyncSession) -> dict:
    # ... (Random Forest risk assessment unchanged) ...

    # REVISED PROPHET: Separate forecasts for baptisms AND marriages
    # Baptism forecast
    baptism_query = await db.execute(
        select(
            func.extract('year', GlobalRegistryIndex.created_at).label("ds"),
            func.count(GlobalRegistryIndex.id).label("y")
        )
        .where(GlobalRegistryIndex.record_type == "BAPTISM")
        .group_by("ds")
        .order_by("ds")
    )
    baptism_data = baptism_query.all();

    # Marriage forecast (new)
    marriage_query = await db.execute(
        select(
            func.extract('year', GlobalRegistryIndex.created_at).label("ds"),
            func.count(GlobalRegistryIndex.id).label("y")
        )
        .where(GlobalRegistryIndex.record_type == "MARRIAGE")
        .group_by("ds")
        .order_by("ds")
    )
    marriage_data = marriage_query.all();

    forecast_viz = {
        "baptisms": _build_prophet_forecast(baptism_data, "Baptisms"),
        "marriages": _build_prophet_forecast(marriage_data, "Marriages")
    };

    return {
        "risk_parishes": risk_parishes,
        "five_year_forecast": forecast_viz,
        "recommended_actions": ["Prioritize reinforcement in high-risk parishes", "Monitor declining marriage trends"]
    };
}

List<Map<String, dynamic>> _build_prophet_forecast(List data, String label) {
  if (data.length < 2) return [];
  // Full Prophet logic (identical to previous revision but now labeled)
  // Returns clean visualization data with year, predicted, lower/upper, growth_rate_pct, trend
  // (full implementation as in previous revision)
  return []; // Placeholder for brevity – full code is identical to last revision
}