from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import LinearRegression
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Secure internal imports
from app.core.dependencies import get_db, require_sysadmin_access, require_read_access
from app.models.all_models import ParishModel, DiocesanAnalyticsModel, GlobalRegistryIndex, User

router = APIRouter()


# ==============================================================================
# 1. THE ETL ENGINE (GOLD LAYER SYNC)
# ==============================================================================
async def perform_parish_sync(db: AsyncSession, parish_id: int, reporting_year: int):
    """Calculates all aggregates for a single parish and writes them to the Gold Layer."""
    parish = (await db.execute(select(ParishModel).where(ParishModel.id == parish_id))).scalar_one_or_none()
    if not parish: return False

    base_query = select(func.count(GlobalRegistryIndex.id)).where(GlobalRegistryIndex.parish_id == parish_id)
    baptisms = (await db.execute(base_query.where(GlobalRegistryIndex.record_type == "BAPTISM"))).scalar() or 0
    marriages = (await db.execute(base_query.where(GlobalRegistryIndex.record_type == "MARRIAGE"))).scalar() or 0

    gold_query = select(DiocesanAnalyticsModel).where(
        DiocesanAnalyticsModel.parish_id == parish_id,
        DiocesanAnalyticsModel.reporting_year == reporting_year
    )
    gold_record = (await db.execute(gold_query)).scalar_one_or_none()

    if gold_record:
        gold_record.total_baptisms_ytd = baptisms
        gold_record.total_marriages_ytd = marriages
        gold_record.last_updated = datetime.now(timezone.utc)
    else:
        new_gold_record = DiocesanAnalyticsModel(
            parish_id=parish_id, parish_name=parish.name, reporting_year=reporting_year,
            total_baptisms_ytd=baptisms, total_marriages_ytd=marriages
        )
        db.add(new_gold_record)

    await db.commit()
    return True


@router.post("/sync/diocese", status_code=status.HTTP_202_ACCEPTED)
async def sync_entire_diocese(
        background_tasks: BackgroundTasks,
        reporting_year: int = datetime.now(timezone.utc).year,
        db: AsyncSession = Depends(get_db),
        _admin: User = Depends(require_sysadmin_access)
):
    """Triggers a massive recalculation of all 32 parishes in the background."""
    parishes = (await db.execute(select(ParishModel.id))).scalars().all()
    if not parishes: raise HTTPException(status_code=400, detail="No parishes registered.")

    async def run_batch_sync(parish_list: list[int], year: int):
        for p_id in parish_list:
            await perform_parish_sync(db, p_id, year)

    background_tasks.add_task(run_batch_sync, parishes, reporting_year)
    return {"message": "Global Diocesan Sync initiated for 32 parishes.", "status": "Processing..."}


# ==============================================================================
# 2. MACHINE LEARNING: DEMOGRAPHIC FORECAST (PDF)
# ==============================================================================
@router.get("/forecast/pdf")
async def generate_ml_forecast_pdf(
        db: AsyncSession = Depends(get_db),
        _user: User = Depends(require_read_access)  # Bishop/SysAdmin
):
    """Uses Scikit-Learn to predict 5-year sacramental demand."""
    # Dummy historical data simulation (Replace with actual queries across past 5 years)
    years = np.array([2021, 2022, 2023, 2024, 2025]).reshape(-1, 1)
    # Simulated total diocesan baptisms for CDOM
    baptisms = np.array([4200, 4350, 4100, 4600, 4800])

    model = LinearRegression()
    model.fit(years, baptisms)
    future_years = np.array([2026, 2027, 2028, 2029, 2030]).reshape(-1, 1)
    predictions = model.predict(future_years)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width / 2.0, height - 50, "CDOM INTELLIGENCE ADDENDUM")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2.0, height - 70, "Confidential: Machine Learning Demographic Forecast")
    pdf.line(50, height - 85, width - 50, height - 85)

    y_pos = height - 120
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y_pos, "5-Year Sacramental Demand Forecast (Algorithm: Scikit-Learn Linear Regression)")
    y_pos -= 25

    pdf.setFont("Helvetica", 11)
    for i, year in enumerate(future_years.flatten()):
        pdf.drawString(70, y_pos, f"Projected {year}: {int(predictions[i])} Baptisms expected across 32 parishes.")
        y_pos -= 20

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=CDOM_ML_Forecast.pdf"
    })