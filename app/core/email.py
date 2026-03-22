import resend
import base64
from app.core.config import settings

# Initialize the Resend SDK with your secure key
resend.api_key = settings.RESEND_API_KEY


def send_system_email(subject: str, email_to: str, html_body: str, pdf_path: str = None):
    """
    Sends an official CDOM email via Resend API.
    Optionally attaches a PDF document.
    """
    attachments = []

    # If a PDF path is provided, read the file and encode it for the email
    if pdf_path:
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        attachments.append({
            "filename": pdf_path.split("/")[-1],  # Extracts just the filename from the path
            "content": list(pdf_data)  # Resend requires raw bytes to be passed as a list
        })

    params: resend.Emails.SendParams = {
        "from": "CDOM System <sysadmin@domansa.org>",  # Ensure this domain is verified in Step 1!
        "to": [email_to],
        "subject": subject,
        "html": html_body,
        "attachments": attachments
    }

    try:
        email_response = resend.Emails.send(params)
        return {"status": "success", "id": email_response["id"]}
    except Exception as e:
        print(f"Failed to send email: {e}")
        return {"status": "error", "message": str(e)}