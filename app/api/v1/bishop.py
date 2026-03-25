import io
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

# Secure internal imports (NOW USING require_bishop_access!)
from app.core.dependencies import get_db, require_bishop_access
from app.models.all_models import DiocesanAnalyticsModel, ParishModel, DeaneryModel, User

# Machine Learning Import
from app.ml.financial_forecaster import predict_next_year_contributions

router = APIRouter()


# ==============================================================================
# 1. LIVE DASHBOARD: THE GRAND OVERVIEW (JSON)
# ==============================================================================
@router.get("/overview", response_model=Dict[str, Any])
async def get_diocesan_grand_totals(
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)  # <--- Centralized Security
):
    """Calculates the absolute totals for the entire Diocese of Mansa."""
    query = select(
        func.sum(DiocesanAnalyticsModel.total_baptisms_ytd).label("total_baptisms"),
        func.sum(DiocesanAnalyticsModel.total_communions_ytd).label("total_communions"),
        func.sum(DiocesanAnalyticsModel.total_confirmations_ytd).label("total_confirmations"),
        func.sum(DiocesanAnalyticsModel.total_marriages_ytd).label("total_marriages"),
        func.sum(DiocesanAnalyticsModel.total_deaths_ytd).label("total_deaths"),
        func.sum(DiocesanAnalyticsModel.diocesan_contributions_target_ytd).label("total_target"),
        func.sum(DiocesanAnalyticsModel.diocesan_contributions_actual_ytd).label("total_actual")
    )

    result = (await db.execute(query)).one()

    target = result.total_target or 0.00
    actual = result.total_actual or 0.00

    return {
        "diocese_name": "Catholic Diocese of Mansa",
        "sacramental_totals": {
            "baptisms": result.total_baptisms or 0,
            "first_communions": result.total_communions or 0,
            "confirmations": result.total_confirmations or 0,
            "marriages": result.total_marriages or 0,
            "deaths": result.total_deaths or 0,
        },
        "financial_health": {
            "total_diocesan_target_zmw": float(target),
            "total_diocesan_actual_zmw": float(actual),
            "overall_variance_zmw": float(actual - target),
            "collection_rate_percentage": round((float(actual) / float(target) * 100), 2) if target > 0 else 0.00
        }
    }


# ==============================================================================
# 2. LIVE DASHBOARD: DEANERY LEADERBOARD (JSON)
# ==============================================================================
@router.get("/deaneries-performance", response_model=Dict[str, Any])
async def get_deaneries_comparative_performance(
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)  # <--- Centralized Security
):
    """Groups the analytics by Deanery to identify regional performance."""
    query = (
        select(
            DeaneryModel.name.label("deanery_name"),
            func.sum(DiocesanAnalyticsModel.total_baptisms_ytd).label("baptisms"),
            func.sum(DiocesanAnalyticsModel.total_marriages_ytd).label("marriages"),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_target_ytd).label("target"),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_actual_ytd).label("actual")
        )
        .select_from(DiocesanAnalyticsModel)
        .join(ParishModel, DiocesanAnalyticsModel.parish_id == ParishModel.id)
        .join(DeaneryModel, ParishModel.deanery_id == DeaneryModel.id)
        .group_by(DeaneryModel.name)
        .order_by(DeaneryModel.name)
    )

    results = (await db.execute(query)).all()

    leaderboard = []
    for row in results:
        target = row.target or 0.00
        actual = row.actual or 0.00
        variance = float(actual - target)

        collection_rate = (float(actual) / float(target) * 100) if target > 0 else 0
        health_status = "EXCELLENT" if collection_rate >= 90 else "WARNING" if collection_rate >= 50 else "CRITICAL"

        leaderboard.append({
            "deanery_name": row.deanery_name,
            "growth_metrics": {
                "baptisms": row.baptisms or 0,
                "marriages": row.marriages or 0,
            },
            "financial_metrics": {
                "target_zmw": float(target),
                "actual_zmw": float(actual),
                "variance_zmw": variance,
                "health_status": health_status
            }
        })

    return {
        "report_type": "Comparative Deanery Performance",
        "data": leaderboard
    }


# ==============================================================================
# 3. PHYSICAL OUTPUT: STATE OF THE DIOCESE REPORT (PDF)
# ==============================================================================
@router.get("/report/pdf")
async def generate_state_of_diocese_report(
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)  # <--- Centralized Security
):
    """Generates the official 'State of the Diocese' PDF report."""
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
    )

    result = query.one()
    current_time = datetime.now(timezone.utc)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- Header ---
    p.setFillColor(colors.darkblue)
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width / 2.0, height - 3 * cm, "CATHOLIC DIOCESE OF MANSA")

    p.setFillColor(colors.black)
    p.setFont("Helvetica", 14)
    p.drawCentredString(width / 2.0, height - 4 * cm, f"State of the Diocese Report - {current_time.year}")

    p.setLineWidth(1)
    p.line(2 * cm, height - 4.5 * cm, width - 2 * cm, height - 4.5 * cm)

    # --- Sacramental Statistics ---
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 6 * cm, "1. Sacramental & Pastoral Growth (YTD)")

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 7 * cm, f"Total Baptisms: {result.total_baptisms or 0}")
    p.drawString(3 * cm, height - 7.6 * cm, f"First Communions: {result.total_communions or 0}")
    p.drawString(3 * cm, height - 8.2 * cm, f"Confirmations: {result.total_confirmations or 0}")
    p.drawString(3 * cm, height - 8.8 * cm, f"Holy Matrimony: {result.total_marriages or 0}")
    p.drawString(3 * cm, height - 9.4 * cm, f"Liber Defunctorum (Deaths): {result.total_deaths or 0}")

    # --- Financial Health ---
    target_zmw = result.total_target or 0.00
    actual_zmw = result.total_actual or 0.00
    variance_zmw = actual_zmw - target_zmw

    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 11.4 * cm, "2. Diocesan Financial Health (Umutulo & Collections)")

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 12.4 * cm, f"Total CDOM Target: ZMW {target_zmw:,.2f}")
    p.drawString(3 * cm, height - 13.0 * cm, f"Total CDOM Collected: ZMW {actual_zmw:,.2f}")

    if variance_zmw >= 0:
        p.setFillColor(colors.darkgreen)
        status_text = "Surplus"
    else:
        p.setFillColor(colors.red)
        status_text = "Deficit"

    p.drawString(3 * cm, height - 13.8 * cm, f"Variance ({status_text}): ZMW {variance_zmw:,.2f}")

    # --- Footer ---
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(2 * cm, 2 * cm,
                 f"Generated automatically by CDOM Management System on {current_time.strftime('%Y-%m-%d %H:%M')} UTC")

    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=CDOM_State_of_Diocese_{current_time.year}.pdf"
    })


# ==============================================================================
# 4. PREDICTIVE ANALYTICS: ML FORECASTING
# ==============================================================================
@router.get("/forecast/financials")
async def get_financial_forecast(
        fund_name: str = "Umutulo waku Diocese",
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)  # <--- Centralized Security
):
    """
    Uses the Machine Learning model to forecast the next year's financial
    contributions based on historical database trends.
    """
    try:
        forecast = await predict_next_year_contributions(db, fund_name)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML Forecasting Error: {str(e)}")