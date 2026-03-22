import io
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import BaptismModel, ParishModel

router = APIRouter()


# ==========================================
# 1. GENERATE BAPTISMAL CERTIFICATE (PDF)
# ==========================================
@router.get("/baptism/{record_id}")
async def generate_baptism_certificate(
        record_id: str,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """
    Generates an official, QR-coded Baptismal Certificate.
    Automatically routes to the correct Parish Schema based on the logged-in user.
    """
    # 1. Secure Tenant Routing
    parish_query = await db.execute(
        select(ParishModel).where(ParishModel.id == _current_user["parish_id"])
    )
    parish = parish_query.scalar_one_or_none()
    await db.execute(text(f'SET search_path TO "{parish.schema_name}", public'))

    # 2. Fetch the Record
    result = await db.execute(select(BaptismModel).where(BaptismModel.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Baptismal record not found.")

    # 3. Initialize PDF Buffer
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- Draw Certificate Borders & Header ---
    p.setStrokeColorRGB(0.1, 0.1, 0.4)  # Deep Blue
    p.rect(1 * cm, 1 * cm, width - 2 * cm, height - 2 * cm, stroke=1, fill=0)

    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(width / 2, height - 4 * cm, "CATHOLIC DIOCESE OF MANSA")

    p.setFont("Helvetica", 16)
    p.drawCentredString(width / 2, height - 5 * cm, f"Parish: {parish.name}")

    p.setFont("Times-Italic", 28)
    p.drawCentredString(width / 2, height - 8 * cm, "Certificate of Baptism")

    # --- Record Details ---
    p.setFont("Helvetica", 12)
    y = height - 11 * cm
    details = [
        f"This is to certify that: {record.first_name} {record.middle_name or ''} {record.last_name}",
        f"Born on: {record.dob}",
        f"Was Baptized on: {record.date_of_baptism}",
        f"By Minister: {record.minister_of_baptism}",
        f"Father: {record.father_first_name} {record.father_last_name}",
        f"Mother: {record.mother_first_name} {record.mother_last_name}",
        f"Godparents: {record.godparents}",
    ]

    for line in details:
        p.drawString(3 * cm, y, line)
        y -= 1 * cm

    # --- Canonical Reference ---
    p.setFont("Helvetica-Bold", 10)
    p.drawString(3 * cm, 4 * cm, f"Canonical Ref: {record.formatted_number}")

    # --- Cryptographic QR Code Verification ---
    # In production, link this to your verification web portal
    verify_url = f"https://verify.domansa.org/check/{record.id}"
    qr = qrcode.QRCode(box_size=3)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    # Place QR Code on PDF
    p.drawInlineImage(img_qr, width - 6 * cm, 3 * cm, width=3 * cm, height=3 * cm)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width - 4.5 * cm, 2.8 * cm, "Scan to Verify")

    # --- Finalize ---
    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Baptism_{record.last_name}.pdf"}
    )