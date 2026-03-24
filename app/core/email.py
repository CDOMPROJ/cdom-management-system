import resend
from app.core.config import settings
import logging

# Initialize Resend with your API key from the .env file
resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. GENERAL SYSTEM COMMUNICATIONS
# ==============================================================================
def send_system_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Generic function to send system alerts, newsletters, or pastoral communications.
    Used primarily by the communications router.
    """
    try:
        response = resend.Emails.send({
            "from": "CDOM System <admin@your-verified-domain.com>",
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        logger.info(f"System email successfully sent to {to_email}. Resend ID: {response.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send system email to {to_email}: {str(e)}")
        return False


# ==============================================================================
# 2. ZERO TRUST PROVISIONING INVITATIONS
# ==============================================================================
def send_invitation_email(to_email: str, role: str, invite_token: str) -> bool:
    """
    Sends a beautifully formatted HTML invitation email to the newly provisioned user.
    """
    # The frontend URL where the user will set their password
    # In production, this would be https://app.cdom.org/setup
    setup_link = f"http://localhost:3000/setup?token={invite_token}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ background-color: #1e3a8a; color: #ffffff; padding: 30px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
            .content {{ padding: 30px; color: #334155; line-height: 1.6; }}
            .content p {{ margin-bottom: 20px; font-size: 16px; }}
            .role-badge {{ display: inline-block; background-color: #e0e7ff; color: #3730a3; padding: 4px 12px; border-radius: 9999px; font-size: 14px; font-weight: 600; }}
            .button {{ display: block; width: 200px; margin: 30px auto; padding: 14px 20px; background-color: #ea580c; color: #ffffff; text-align: center; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; }}
            .button:hover {{ background-color: #c2410c; }}
            .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Catholic Diocese of Mansa</h1>
            </div>
            <div class="content">
                <p>Peace be with you,</p>
                <p>You have been invited by the System Administrator to join the CDOM Digital Registry system. Your account has been provisioned with the following access level:</p>
                <p style="text-align: center;"><span class="role-badge">{role.upper()}</span></p>
                <p>To finalize your account, secure your access, and set your private password, please click the button below. <strong>This link will expire in 48 hours.</strong></p>

                <a href="{setup_link}" class="button">Complete Account Setup</a>

                <p>If you did not expect this invitation, please contact the Diocesan Curia immediately.</p>
            </div>
            <div class="footer">
                &copy; 2026 Catholic Diocese of Mansa. All rights reserved.<br>
                This is an automated security message. Do not reply to this email.
            </div>
        </div>
    </body>
    </html>
    """

    try:
        response = resend.Emails.send({
            "from": "CDOM Registry <admin@your-verified-domain.com>",
            "to": [to_email],
            "subject": "Action Required: CDOM Registry Account Setup",
            "html": html_content
        })
        logger.info(f"Invitation email successfully sent to {to_email}. Resend ID: {response.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False