import numpy as np
from sklearn.linear_model import LinearRegression
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.all_models import DiocesanContributionModel

async def predict_next_year_contributions(db: AsyncSession, fund_name: str = "Umutulo"):
    """
    Uses Simple Linear Regression to forecast future diocesan contributions
    based on historical data across all parishes.
    """
    # 1. Fetch aggregated historical data grouped by year
    query = await db.execute(
        select(
            DiocesanContributionModel.reporting_year,
            func.sum(DiocesanContributionModel.actual_amount).label("total_amount")
        )
        .where(DiocesanContributionModel.fund_name == fund_name)
        .group_by(DiocesanContributionModel.reporting_year)
        .order_by(DiocesanContributionModel.reporting_year)
    )
    records = query.all()

    # We need at least 2 data points (years) to draw a regression line
    if len(records) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 2 years of data to forecast {fund_name}.",
            "historical_data_points": len(records)
        }

    # 2. Prepare the data for scikit-learn
    years = np.array([r.reporting_year for r in records]).reshape(-1, 1)
    amounts = np.array([float(r.total_amount) for r in records])

    # 3. Train the Linear Regression Model
    model = LinearRegression()
    model.fit(years, amounts)

    # 4. Predict the next year
    next_year = int(years[-1][0]) + 1
    predicted_amount = model.predict([[next_year]])[0]

    # Calculate projected growth rate
    current_amount = amounts[-1]
    growth_rate = ((predicted_amount - current_amount) / current_amount) * 100 if current_amount != 0 else 0

    return {
        "status": "success",
        "fund_name": fund_name,
        "historical_trend": [{"year": int(y[0]), "amount": a} for y, a in zip(years, amounts)],
        "forecast": {
            "predicted_year": next_year,
            "predicted_amount_zmw": round(predicted_amount, 2),
            "projected_growth_rate_percentage": round(growth_rate, 2),
            "trend": "Upward" if growth_rate > 0 else "Downward"
        }
    }