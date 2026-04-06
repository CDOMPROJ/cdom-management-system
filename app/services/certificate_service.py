from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from fastapi import BackgroundTasks
from app.core.config import settings
import uuid
import os

class CertificateService:
    @staticmethod
    async def generate_baptism_certificate(
        baptism_data: dict,
        background_tasks: BackgroundTasks
    ) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, alignment=1, spaceAfter=30)
        normal_style = styles['Normal']

        elements = []

        # Header - Diocesan Seal / Title
        elements.append(Paragraph(f"<b>CATHOLIC DIOCESE OF MANSA</b>", title_style))
        elements.append(Paragraph("Certificate of Baptism", styles['Heading1']))
        elements.append(Spacer(1, 0.5 * inch))

        # Baptism Details Table
        data = [
            ["Canonical Number:", baptism_data.get("formatted_number", "N/A")],
            ["Full Name:", f"{baptism_data.get('first_name', '')} {baptism_data.get('middle_name', '')} {baptism_data.get('last_name', '')}"],
            ["Date of Birth:", str(baptism_data.get('date_of_birth', 'N/A'))],
            ["Date of Baptism:", str(baptism_data.get('date_of_baptism', 'N/A'))],
            ["Place of Baptism:", baptism_data.get('parish_name', 'N/A')],
            ["Father's Name:", baptism_data.get('father_name', 'N/A')],
            ["Mother's Name:", baptism_data.get('mother_name', 'N/A')],
            ["Godparents:", baptism_data.get('godparents', 'N/A')],
        ]

        table = Table(data, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph("This certifies that the above-named person received the Sacrament of Baptism.", normal_style))

        doc.build(elements)
        buffer.seek(0)

        # Optional: Save to disk for audit (background)
        background_tasks.add_task(
            CertificateService._save_certificate_to_disk,
            buffer.getvalue(),
            f"baptism_{baptism_data.get('formatted_number')}.pdf"
        )

        return buffer

    @staticmethod
    def _save_certificate_to_disk(pdf_bytes: bytes, filename: str):
        os.makedirs("certificates", exist_ok=True)
        with open(f"certificates/{filename}", "wb") as f:
            f.write(pdf_bytes)

    # Similar methods can be added for Marriage, Confirmation, etc.