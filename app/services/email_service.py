import resend
from fastapi import BackgroundTasks
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY

class EmailService:
    @staticmethod
    async def send_sacrament_notification(
        recipient_email: str,
        sacrament_type: str,
        canonical_number: str,
        recipient_name: str,
        background_tasks: BackgroundTasks
    ):
        """Send confirmation email using Resend (background task)."""
        subject = f"CDOM - {sacrament_type} Registered"
        body = f"""
        Dear {recipient_name},

        Your {sacrament_type} record has been successfully registered in the Diocesan system.

        Canonical Reference: {canonical_number}

        You can view your certificate at: https://cdom-app.web.app/certificates/{canonical_number}

        In Christ,
        The Chancery
        Catholic Diocese of Mansa
        """

        def send_email_task():
            resend.Emails.send({
                "from": "Chancery <no-reply@cdom.org>",
                "to": recipient_email,
                "subject": subject,
                "html": f"<pre>{body}</pre>"
            })

        background_tasks.add_task(send_email_task)