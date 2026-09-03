"""
Outbound email for the Platform Admin's notification inbox.

Two things drive an email here: every meaningful mutating action anywhere
in ACEWIN (app/audit.py:record_action, source="api") and every support
request a tenant user files (app/routers/support_requests.py). Both also
land in the Platform Admin panel's "Requests" tab (app/routers/
platform_admin.py) -- email is a *notification*, the panel is the system
of record, so a failed or skipped send never loses anything.

Deliberately modeled on app.audit.record_action's own failure contract:
`send_admin_notification` never raises. If SMTP_HOST isn't configured
(the default -- see app/config.py), it logs and returns instead of
attempting a connection, so local/dev and any deployment that hasn't set
up SMTP yet keep working exactly as before this module existed.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("acewin.email")


def send_admin_notification(subject: str, body: str) -> bool:
    """Best-effort send of a plain-text email to every address in
    settings.admin_notification_email_list. Returns whether it actually
    sent (False both on skip-because-unconfigured and on real failure) --
    callers that only fire-and-forget can ignore the return value."""
    recipients = settings.admin_notification_email_list
    if not recipients:
        logger.info("Admin notification skipped (no admin recipients configured): %s", subject)
        return False
    if not settings.smtp_host:
        logger.info("Admin notification skipped (SMTP_HOST not configured): %s", subject)
        return False

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, recipients, msg.as_string())
        return True
    except Exception:
        # Never let a notification-email failure surface to the caller --
        # the CRM action or support request it's describing already
        # succeeded and must not appear to fail because of this.
        logger.exception("Failed to send admin notification email: %s", subject)
        return False
