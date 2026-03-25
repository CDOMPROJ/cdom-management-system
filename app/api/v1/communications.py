from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
import os

# Secure internal imports
from app.core.dependencies import require_read_access
from app.core.email import send_system_email
from app.models.all_models import User

router = APIRouter()

# Schema for incoming email requests
class EmailRequest(BaseModel):
    email_to: EmailStr
    subject: str = "CDOM System Alert"
    body: str = "This is an automated message from the CDOM Management System."
    include_dummy_pdf: bool = False

# ==============================================================================
# 1. DISPATCH SYSTEM EMAIL (BACKGROUND TASK)
# ==============================================================================
@router.post("/send", status_code=status.HTTP_200_OK)
async def dispatch_email(
        email_in: EmailRequest,
        background_tasks: BackgroundTasks, # <-- Inject the Background Worker
        _current_user: User = Depends(require_read_access) # Ensure strict User object
):
    """
    Dispatches an official system email via the Resend API.
    Offloads the HTTP request to a Background Task to prevent UI latency.
    """
    pdf_path = None

    # Generate a temporary dummy PDF synchronously if requested
    if email_in.include_dummy_pdf:
        pdf_path = "temp_test_certificate.pdf"
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

        # Hand the email dispatch off to the background thread!
        # The user's screen will not freeze waiting for this to finish.
        background_tasks.add_task(
            send_system_email,
            subject=email_in.subject,
            email_to=email_in.email_to,
            html_body=html_content,
            pdf_path=pdf_path
        )

        return {
            "message": "Email queued for dispatch successfully.",
            "status": "Processing in background"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))