import io
import qrcode
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
import uuid

# PHASE 3 SECURE IMPORTS (replacing old dependencies)
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import BaptismModel, MarriageModel, ParishModel, User

router = APIRouter()

ownership_service = OwnershipService()


# ==============================================================================
# HELPER: DRAW CERTIFICATE BORDER & HEADER & QR CODE
# ==============================================================================
def draw_certificate_template(p: canvas.Canvas, width: float, height: float, title: str, parish_name: str,
                              verify_url: str):
    """Draws the standard borders, headers, and cryptographic QR seal."""
    # 1. Outer & Inner Borders
    p.setLineWidth(3)
    p.setStrokeColor(colors.darkblue)
    p.rect(1 * cm, 1 * cm, width - 2 * cm, height - 2 * cm)
    p.setLineWidth(1)
    p.rect(1.2 * cm, 1.2 * cm, width - 2.4 * cm, height - 2.4 * cm)

    # 2. Diocesan Header
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2.0, height - 3 * cm, "CATHOLIC DIOCESE OF MANSA")
    p.setFont("Helvetica", 14)
    p.drawCentredString(width / 2.0, height - 3.8 * cm, parish_name.upper())

    # 3. Certificate Title
    p.setFont("Helvetica-Bold", 22)
    p.setFillColor(colors.darkblue)
    p.drawCentredString(width / 2.0, height - 5.5 * cm, title.upper())
    p.setStrokeColor(colors.black)
    p.setLineWidth(1)
    p.line(4 * cm, height - 5.8 * cm, width - 4 * cm, height - 5.8 * cm)
    p.setFillColor(colors.black)

    # 4. Cryptographic QR Code Verification
    qr = qrcode.QRCode(box_size=3)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    # Draw QR in the top right corner
    p.drawInlineImage(img_qr, width - 5 * cm, height - 5 * cm, width=3 * cm, height=3 * cm)


# ==============================================================================
# 1. GENERATE BAPTISM CERTIFICATE (WITH QR)
# ==============================================================================
@router.get("/baptism/{record_id}")
async def generate_baptism_certificate(
        record_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Generates an official, print-ready Certificate of Baptism with QR verification."""
    # PHASE 3 ABAC ENFORCEMENT
    await PermissionChecker("parish:read")(current_user)

    query = select(BaptismModel).where(BaptismModel.id == record_id)
    record = (await db.execute(query)).scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Baptism record not found.")

    # PHASE 3 OBJECT-LEVEL OWNERSHIP CHECK
    await ownership_service.check_ownership(record, current_user)

    parish_name = "Parish Registry"
    if current_user.parish_id:
        p_query = select(ParishModel.name).where(ParishModel.id == current_user.parish_id)
        parish_name = (await db.execute(p_query)).scalar_one_or_none() or "Parish Registry"

    verify_url = f"https://verify.domansa.org/check/baptism/{record.id}"

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    draw_certificate_template(p, width, height, "Certificate of Baptism", parish_name, verify_url)

    # --- BODY TEXT ---
    p.setFont("Helvetica", 14)
    p.drawString(3 * cm, height - 8 * cm, "This is to certify that:")

    p.setFont("Helvetica-Bold", 16)
    full_name = f"{record.first_name} {record.middle_name or ''} {record.last_name}".strip()
    p.drawCentredString(width / 2.0, height - 9.5 * cm, full_name.upper())

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 11 * cm,
                 f"Child of: {record.father_first_name} {record.father_last_name} and {record.mother_first_name} {record.mother_last_name}")
    p.drawString(3 * cm, height - 12 * cm, f"Born on: {record.dob.strftime('%d %B %Y')} at {record.village}")
    p.drawString(3 * cm, height - 14 * cm, "Was Baptized According to the Rite of the Roman Catholic Church on:")

    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2.0, height - 15 * cm, record.date_of_baptism.strftime('%d %B %Y'))

    p.setFont("Helvetica", 12)
    p.drawString(3 * cm, height - 17 * cm, f"By the Rev. Minister: {record.minister_of_baptism}")
    p.drawString(3 * cm, height - 18 * cm, f"Sponsors / Godparents: {record.godparents}")

    # --- FOOTER & SIGNATURES ---
    p.setFont("Helvetica", 10)
    p.drawString(3 * cm, height - 21 * cm, f"Canonical Register No: {record.formatted_number}")
    p.drawString(3 * cm, height - 21.5 * cm, f"Issued Date: {datetime.now(timezone.utc).strftime('%d %B %Y')}")

    p.line(12 * cm, height - 23 * cm, 18 * cm, height - 23 * cm)
    p.drawCentredString(15 * cm, height - 23.5 * cm, "Parish Priest Signature & Seal")

    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=Baptism_Certificate_{record.formatted_number.replace('/', '-')}.pdf"
    })