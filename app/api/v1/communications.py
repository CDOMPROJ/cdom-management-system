from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel, EmailStr
from app.core.dependencies import require_read_access
from app.core.email import send_system_email
import os

router = APIRouter()


# Schema for incoming email requests
class EmailRequest(BaseModel):
    email_to: EmailStr
    subject: str = "CDOM System Alert"
    body: str = "This is an automated message from the CDOM Management System."
    include_dummy_pdf: bool = False


@router.post("/send", status_code=status.HTTP_200_OK)
async def dispatch_email(
        email_in: EmailRequest,
        _current_user: dict = Depends(require_read_access)
):
    """
    Dispatches an official system email via the Resend API.
    Can optionally generate and attach a dummy PDF to verify attachment logic.
    """
    pdf_path = None

    # Generate a temporary dummy PDF for testing the attachment pipes
    if email_in.include_dummy_pdf:
        pdf_path = "temp_test_certificate.pdf"
        # We are just writing text into a .pdf extension for rapid testing
        with open(pdf_path, "w") as f:
            f.write("CDOM Official Dummy Certificate.\nReplace this with real Gold Layer PDF generation later.")

    try:
        # Wrap the body in some basic HTML to make it look professional
        html_content = f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #2c3e50;">{email_in.subject}</h2>
            <p>{email_in.body}</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888;">
                Catholic Diocese of Mansa (CDOM) Management System<br>
                Do not reply to this automated message.
            </p>
        </div>
        """

        # Dispatch using the engine we built earlier
        response = send_system_email(
            subject=email_in.subject,
            email_to=email_in.email_to,
            html_body=html_content,
            pdf_path=pdf_path
        )

        if response.get("status") == "error":
            raise HTTPException(status_code=500, detail=response.get("message"))

        return {
            "message": "Email dispatched successfully",
            "resend_id": response.get("id"),
            "attached_dummy_pdf": email_in.include_dummy_pdf
        }

    finally:
        # The Cleanup: Delete the dummy file so we don't clutter the server
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)