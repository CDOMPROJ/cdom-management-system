import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

from app.core.dependencies import get_db, require_bishop_access
from app.models.all_models import DiocesanAnalyticsModel
from app.ml.financial_forecaster import predict_next_year_contributions

router = APIRouter()


@router.get("/report/pdf")
async def generate_state_of_diocese_report(
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_bishop_access)
):
    """
    Generates the official 'State of the Diocese' PDF report.
    Exclusive to the Bishop. Aggregates data from all 32 parishes.
    """
    # 1. Fetch Global Aggregates across the entire Diocese
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

    # Fallbacks in case the DB is completely empty
    baptisms = result.total_baptisms or 0
    communions = result.total_communions or 0
    confirmations = result.total_confirmations or 0
    marriages = result.total_marriages or 0
    deaths = result.total_deaths or 0
    target_zmw = result.total_target or 0
    actual_zmw = result.total_actual or 0
    variance_zmw = actual_zmw - target_zmw

    # 2. Generate the PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Modern, timezone-aware datetime
    current_time = datetime.now(timezone.utc)

    # Header section
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 2.5 * cm, "CATHOLIC DIOCESE OF MANSA")

    p.setFont("Helvetica", 14)
    p.drawCentredString(width / 2, height - 3.5 * cm, "Office of the Bishop")

    p.setFont("Helvetica-Oblique", 12)
    p.drawCentredString(width / 2, height - 4.5 * cm, f"State of the Diocese Report - {current_time.year}")

    # Divider line
    p.setLineWidth(1)
    p.line(2 * cm, height - 5 * cm, width - 2 * cm, height - 5 * cm)

    # Pastoral Health Section
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 6.5 * cm, "1. Pastoral Health (Sacramental Totals)")

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 7.5 * cm, f"Total Baptisms: {baptisms}")
    p.drawString(3 * cm, height - 8.2 * cm, f"Total First Communions: {communions}")
    p.drawString(3 * cm, height - 8.9 * cm, f"Total Confirmations: {confirmations}")
    p.drawString(3 * cm, height - 9.6 * cm, f"Total Marriages: {marriages}")
    p.drawString(3 * cm, height - 10.3 * cm, f"Total Funerals: {deaths}")

    # Financial Health Section
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 12 * cm, "2. Financial Health (Obligatory Contributions)")

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 13 * cm, f"Total CDOM Target: ZMW {target_zmw:,.2f}")
    p.drawString(3 * cm, height - 13.7 * cm, f"Total Remitted: ZMW {actual_zmw:,.2f}")

    # Color code the variance
    if variance_zmw >= 0:
        p.setFillColor(colors.darkgreen)
        status_text = "Surplus"
    else:
        p.setFillColor(colors.red)
        status_text = "Deficit"

    p.drawString(3 * cm, height - 14.4 * cm, f"Variance ({status_text}): ZMW {variance_zmw:,.2f}")

    # Reset color and add footer
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(2 * cm, 2 * cm,
                 f"Generated automatically by CDOM Management System on {current_time.strftime('%Y-%m-%d %H:%M')} UTC")

    # Save and send
    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=CDOM_State_of_Diocese_{current_time.year}.pdf"
    })


@router.get("/forecast/financials")
async def get_financial_forecast(
        fund_name: str = "Umutulo",
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_bishop_access)
):
    """
    Executes the Machine Learning forecaster to predict future collections.
    Defaults to Umutulo, but the Bishop can pass any obligatory fund name.
    """
    forecast_data = await predict_next_year_contributions(db, fund_name)

    if forecast_data.get("status") == "insufficient_data":
        raise HTTPException(status_code=400, detail=forecast_data["message"])

    return forecast_data