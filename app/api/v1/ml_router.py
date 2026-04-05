from fastapi import APIRouter, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_read_access
from app.models.all_models import User
from app.ml.financial_forecaster import predict_next_year_contributions

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.get("/forecast/financials", dependencies=[Depends(limiter.limit("10/minute"))])
async def get_financial_forecast(
    fund_name: str = "Umutulo waku Diocese",
    db: AsyncSession = Depends(get_db),
    _bishop: User = Depends(require_read_access)
):
    """ML financial forecast endpoint with rate limiting."""
    forecast = await predict_next_year_contributions(db, fund_name)
    return forecast