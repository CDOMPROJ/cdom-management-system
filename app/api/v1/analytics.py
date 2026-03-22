from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
import numpy as np
from sklearn.linear_model import LinearRegression
import json
import io
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Security: In production, restrict this to Bishops or SysAdmins
from app.core.dependencies import get_db, get_current_user
from app.models.all_models import ParishModel, DemographicTrendModel, BaptismModel

router = APIRouter()

# ==============================================================================
# PHASE 4: THE GOLD LAYER (ETL AGGREGATION ENGINE)
# ==============================================================================
@router.post("/aggregate/{year}")
async def run_annual_aggregation(
        year: int,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_user)
):
    """
    Extracts raw sacramental data from all isolated Parish schemas,
    aggregates the totals for the specified year, and loads them
    into the public Demographic Trends table (Gold Layer) for ML training.
    """
    parishes = (await db.execute(select(ParishModel))).scalars().all()

    if not parishes:
        return {"message": "No parishes found in the network.", "processed": 0}

    results_log = []

    for parish in parishes:
        try:
            await db.execute(text(f'SET search_path TO "{parish.schema_name}"'))

            bap_query = select(func.count(BaptismModel.id)).where(BaptismModel.registry_year == year)
            total_baptisms = await db.scalar(bap_query) or 0

            await db.execute(text('SET search_path TO public'))

            trend_query = select(DemographicTrendModel).where(
                DemographicTrendModel.parish_id == parish.id,
                DemographicTrendModel.year == year
            )
            existing_trend = (await db.execute(trend_query)).scalar_one_or_none()

            if existing_trend:
                existing_trend.baptism_count = total_baptisms
            else:
                new_trend = DemographicTrendModel(
                    parish_id=parish.id,
                    year=year,
                    baptism_count=total_baptisms
                )
                db.add(new_trend)

            results_log.append({"parish": parish.name, "baptisms": total_baptisms})

        except Exception as e:
            print(f"Failed to process {parish.name}: {e}")
            await db.execute(text('SET search_path TO public'))

    await db.commit()
    await db.execute(text(f'SET search_path TO "{_current_user.get("tenant_schema", "public")}", public'))

    return {
        "message": f"Aggregation complete for {year}.",
        "parishes_processed": len(results_log),
        "data": results_log
    }


# ==============================================================================
# PHASE 4: MACHINE LEARNING (PREDICTIVE DEMAND FORECASTING)
# ==============================================================================
@router.post("/predict/{parish_id}")
async def generate_predictions(
        parish_id: int,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_user)
):
    """
    Trains a Linear Regression model on historical parish data to forecast
    future sacramental demand (Baptisms, Confirmations) for the next 5 years.
    """
    query = select(DemographicTrendModel).where(DemographicTrendModel.parish_id == parish_id).order_by(
        DemographicTrendModel.year.asc())
    history = (await db.execute(query)).scalars().all()

    if len(history) < 3:
        return {"message": "Insufficient historical data. The ML model requires at least 3 years of data to train."}

    X = np.array([record.year for record in history]).reshape(-1, 1)
    y = np.array([record.baptism_count for record in history])

    model = LinearRegression()
    model.fit(X, y)

    growth_rate = round(float(model.coef_[0]), 2)

    last_year = history[-1].year
    future_years = np.array([last_year + i for i in range(1, 6)]).reshape(-1, 1)
    predictions = model.predict(future_years)

    forecast_data = {}
    for year, predicted_count in zip(future_years.flatten(), predictions):
        forecast_data[f"Predicted_Baptisms_{year}"] = max(0, int(round(predicted_count)))

    latest_record = history[-1]
    latest_record.projected_youth_growth_rate = growth_rate
    latest_record.predicted_sacrament_demand = forecast_data

    await db.commit()

    return {
        "message": "AI Model successfully trained and predictions generated.",
        "model_metrics": {
            "training_years_used": len(history),
            "calculated_growth_rate": growth_rate
        },
        "forecast": forecast_data
    }


# ==============================================================================
# PHASE 4: THE GOLD LAYER (OFFICIAL DIOCESAN PDF GENERATOR)
# ==============================================================================
@router.get("/report/parish/{parish_id}")
async def generate_parish_pdf_report(
        parish_id: int,
        db: AsyncSession = Depends(get_db),
        # _current_user: dict = Depends(get_current_user) # Commented out for browser testing
):
    """
    Generates a 2-page PDF.
    Page 1: The Official Diocesan Annual Statistics Form (Fixed Layout).
    Page 2: The CDOM AI Demographic Forecast.
    """
    parish = (await db.execute(select(ParishModel).where(ParishModel.id == parish_id))).scalar_one_or_none()
    if not parish:
        return {"message": "Parish not found."}

    query = select(DemographicTrendModel).where(DemographicTrendModel.parish_id == parish_id).order_by(
        DemographicTrendModel.year.desc())
    history = (await db.execute(query)).scalars().all()
    latest_data = history[0] if history else None
    report_year = latest_data.year if latest_data else 2026

    # --- JUST-IN-TIME (JIT) AGE CALCULATION ---
    under_1 = 0
    one_to_seven = 0
    over_seven = 0

    try:
        await db.execute(text(f'SET search_path TO "{parish.schema_name}"'))
        bap_query = select(BaptismModel.dob, BaptismModel.date_of_baptism).where(
            BaptismModel.registry_year == int(report_year))
        bap_results = (await db.execute(bap_query)).all()

        for dob, date_of_baptism in bap_results:
            if dob and date_of_baptism:
                age_days = (date_of_baptism - dob).days
                age_years = age_days / 365.25

                if age_years <= 1.0:
                    under_1 += 1
                elif 1.0 < age_years <= 7.0:
                    one_to_seven += 1
                else:
                    over_seven += 1
    except Exception as e:
        print(f"JIT Calculation Error: {e}")
    finally:
        await db.execute(text('SET search_path TO public'))

    # --- INITIALIZE PDF ---
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ==========================================================================
    # PAGE 1: OFFICIAL COMPLIANCE FORM
    # ==========================================================================
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2.0, height - 50, "CATHOLIC DIOCESE OF MANSA")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width / 2.0, height - 70, f"ANNUAL STATISTICS FOR {report_year}")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(width / 2.0, height - 90, f"{parish.name.upper()}")

    pdf.setFont("Helvetica", 9)
    safe_name = parish.name.replace(' ', '').lower()
    emails = f"PARISH PRIEST: pp{safe_name}@domansa.org  |  SECRETARY: sec{safe_name}@domansa.org"
    pdf.drawCentredString(width / 2.0, height - 105, emails)

    pdf.setLineWidth(1)
    pdf.line(50, height - 115, width - 50, height - 115)

    y = height - 135
    line_spacing = 16
    section_gap = 22
    indent_1 = 50
    indent_2 = 80
    answer_x = 400
    line_length = 50

    def draw_row(text, x_pos, y_pos, value=0):
        pdf.drawString(x_pos, y_pos, text)
        pdf.line(answer_x, y_pos - 2, answer_x + line_length, y_pos - 2)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(answer_x + 15, y_pos, str(value))
        pdf.setFont("Helvetica", 11)

    pdf.setFont("Helvetica", 11)

    # Point 1: Baptisms
    pdf.drawString(indent_1, y, "1. No of those baptized during the year:")
    y -= line_spacing
    draw_row("a) up to 1 year", indent_2, y, value=under_1)
    y -= line_spacing
    draw_row("b) from 1 to 7 years old", indent_2, y, value=one_to_seven)
    y -= line_spacing
    draw_row("c) over 7 years old", indent_2, y, value=over_seven)
    y -= line_spacing

    total_bap = latest_data.baptism_count if latest_data else 0
    draw_row("Total No of Baptisms", indent_2, y, value=total_bap)
    y -= section_gap

    # Point 2: Confirmations
    pdf.drawString(indent_1, y, "2. No of those confirmed during the year:")
    y -= line_spacing
    draw_row("a) Adults", indent_2, y, value=0)
    y -= line_spacing
    draw_row("b) Children", indent_2, y, value=0)
    y -= line_spacing
    draw_row("Total No of confirmations", indent_2, y, value=0)
    y -= section_gap

    # Point 3: Communions
    draw_row("3. No of receipts of first Holy Communion:", indent_1, y, value=0)
    y -= section_gap

    # Point 4: Marriages
    pdf.drawString(indent_1, y, "4. No of Marriages during the year:")
    y -= line_spacing
    draw_row("a) between Catholics", indent_2, y, value=0)
    y -= line_spacing
    draw_row("b) between Catholics/non Catholics:", indent_2, y, value=0)
    y -= line_spacing
    draw_row("Total No of Marriages:", indent_2, y, value=0)
    y -= section_gap

    # Points 5 & 6
    draw_row("5. No of Catechumens:", indent_1, y, value=0)
    y -= section_gap
    draw_row("6. No of converts received into the church (no conditional Bapt.):", indent_1, y, value=0)
    y -= section_gap

    # Point 7: Catechists
    pdf.drawString(indent_1, y, "7. No of Catechists:")
    y -= line_spacing
    draw_row("a) Paid Catechists", indent_2, y, value=0)
    y -= line_spacing
    draw_row("b) Voluntary Catechists", indent_2, y, value=0)
    y -= line_spacing
    draw_row("Total No of Catechists", indent_2, y, value=0)
    y -= section_gap

    # Points 8 & 9
    draw_row("8. Total No of Catholic population:", indent_1, y, value=0)
    y -= section_gap

    pdf.drawString(indent_1, y, "9. No of non Catholics:")
    y -= line_spacing
    draw_row("a) Other Christians:", indent_2, y, value=0)
    y -= line_spacing
    draw_row("b) Non-Christians:", indent_2, y, value=0)

    # --- FOOTER ---
    y_sig = 90
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y_sig, "PARISH PRIEST:")
    pdf.line(140, y_sig - 2, 280, y_sig - 2)
    pdf.drawString(50, y_sig - 25, "DATE:")
    pdf.line(90, y_sig - 27, 280, y_sig - 27)

    pdf.rect(width - 200, y_sig - 40, 150, 60)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(width - 125, y_sig - 10, "[ OFFICIAL PARISH STAMP ]")

    pdf.showPage()

    # ==========================================================================
    # PAGE 2: CDOM INTELLIGENCE
    # ==========================================================================
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2.0, height - 50, "CDOM INTELLIGENCE ADDENDUM")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2.0, height - 70, "Confidential: Machine Learning Demographic Forecast")
    pdf.line(50, height - 85, width - 50, height - 85)

    y_pos = height - 120
    if latest_data and latest_data.predicted_sacrament_demand:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_pos, "5-Year Sacramental Demand Forecast (Algorithm: Scikit-Learn Linear Regression)")
        y_pos -= 25

        pdf.setFont("Helvetica", 11)
        growth_rate = latest_data.projected_youth_growth_rate or 0.0
        trend_word = "Growth" if growth_rate > 0 else "Decline"
        pdf.drawString(70, y_pos, f"Calculated Trajectory: {abs(growth_rate)} {trend_word} Rate")
        y_pos -= 20

        for key, value in latest_data.predicted_sacrament_demand.items():
            year_label = key.split("_")[-1]
            pdf.drawString(70, y_pos, f"Projected {year_label}: {value} Baptisms")
            y_pos -= 20
    else:
        pdf.setFillColor(colors.red)
        pdf.drawString(50, y_pos, "No AI predictions available. Please run the predictive pipeline.")

    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Annual_Statistics_{report_year}_{parish.name.replace(' ', '_')}.pdf"}
    )