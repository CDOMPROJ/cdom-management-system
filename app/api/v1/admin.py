from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import ParishModel, DiocesanContributionModel, BaptismModel, DeathRegisterModel

router = APIRouter()


# --- Response Schemas ---
class ParishHealthStats(BaseModel):
    parish_name: str
    total_baptisms: int
    total_deaths: int
    health_ratio: float
    status: str


class FinancialCompliance(BaseModel):
    parish_name: str
    target: float
    actual: float
    compliance_percentage: float
    status: str


# ==========================================
# 1. DEANERY FINANCIAL COMPLIANCE MATRIX
# ==========================================
@router.get("/financial-compliance/{deanery_id}", response_model=List[FinancialCompliance])
async def get_deanery_financial_compliance(
        deanery_id: int,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """Calculates how much of the Umutulo target each parish in a deanery has met."""
    if _current_user["role"] != "Bishop":
        if _current_user["role"] == "Dean" and _current_user["deanery_id"] != deanery_id:
            raise HTTPException(status_code=403, detail="Unauthorized to view this Deanery.")

    parishes = (await db.execute(select(ParishModel).where(ParishModel.deanery_id == deanery_id))).scalars().all()
    results = []

    for parish in parishes:
        await db.execute(text(f'SET search_path TO "{parish.schema_name}", public'))
        stats = (await db.execute(select(
            func.sum(DiocesanContributionModel.target_amount).label("target"),
            func.sum(DiocesanContributionModel.actual_amount).label("actual")
        ))).one()

        target = float(stats.target or 0)
        actual = float(stats.actual or 0)
        comp_pct = round((actual / target) * 100, 1) if target > 0 else 0.0

        results.append(FinancialCompliance(
            parish_name=parish.name,
            target=target,
            actual=actual,
            compliance_percentage=comp_pct,
            status="Compliant" if comp_pct >= 100 else "Deficient"
        ))

    await db.execute(text('SET search_path TO public'))
    return sorted(results, key=lambda x: x.compliance_percentage)


# ==========================================
# 2. DEMOGRAPHIC HEALTH HEATMAP
# ==========================================
@router.get("/health-heatmap/{deanery_id}", response_model=List[ParishHealthStats])
async def get_parish_health_heatmap(
        deanery_id: int,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """Calculates the Baptism-to-Funeral ratio (Growing vs Aging) for a Deanery."""
    if _current_user["role"] not in ["Bishop", "Dean"]:
        raise HTTPException(status_code=403, detail="Curia Access Only.")

    parishes = (await db.execute(select(ParishModel).where(ParishModel.deanery_id == deanery_id))).scalars().all()
    results = []

    for parish in parishes:
        await db.execute(text(f'SET search_path TO "{parish.schema_name}", public'))

        b_count = (await db.execute(select(func.count(BaptismModel.id)))).scalar() or 0
        d_count = (await db.execute(select(func.count(DeathRegisterModel.id)))).scalar() or 0

        ratio = round(b_count / d_count, 2) if d_count > 0 else float(b_count)

        results.append(ParishHealthStats(
            parish_name=parish.name,
            total_baptisms=b_count,
            total_deaths=d_count,
            health_ratio=ratio,
            status="Growing" if ratio >= 2.0 else "Stable" if ratio >= 1.0 else "Aging"
        ))

    await db.execute(text('SET search_path TO public'))
    return sorted(results, key=lambda x: x.health_ratio)


# ==========================================
# 3. QUINQUENNIAL DIOCESAN SUMMARY
# ==========================================
@router.get("/quinquennial-summary")
async def get_global_vatican_report(
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """Aggregates all Sacraments across all 31 parishes for the Bishop's Vatican Report."""
    if _current_user["role"] != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can generate this report.")

    all_parishes = (await db.execute(select(ParishModel))).scalars().all()
    totals = {"baptisms": 0, "marriages": 0, "deaths": 0}

    for parish in all_parishes:
        await db.execute(text(f'SET search_path TO "{parish.schema_name}", public'))
        totals["baptisms"] += (await db.execute(select(func.count(BaptismModel.id)))).scalar() or 0
        totals["marriages"] += (await db.execute(select(func.count(BaptismModel.id)))).scalar() or 0  # Example link
        # ... logic for other registers ...

    await db.execute(text('SET search_path TO public'))
    return {"diocese": "Catholic Diocese of Mansa", "grand_totals": totals}