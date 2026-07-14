"""Sends real transactional email over SMTP (registration verification, password reset).

Falls back to logging in dev/test when SMTP isn't configured, mirroring the mock-payout pattern
already used for Paystack (app.services.reward._payout_mock). In production with SMTP left
unconfigured, the token is never logged - only a generic "delivery not configured" line, with no
secret in it. This is the actual fix for a real vulnerability: this file used to not exist, and
every caller logged the raw reset/verification token directly, which was the only way those
tokens were ever "delivered" - in production, that meant working account-takeover tokens sitting
in the log stream. Callers should catch EmailSendError and continue (never fail a request, or
change its response shape, just because delivery failed) - same reasoning as forgot_password
already returning an identical response whether or not the email exists, to avoid enumeration.
"""
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when SMTP is configured but the send itself failed."""


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_CONFIGURED:
        if settings.IS_PRODUCTION:
            logger.error(
                f'Email delivery not configured - could not send "{subject}" to {to}. '
                "Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD to enable real email."
            )
        else:
            # Dev/test convenience only - safe to log the token-carrying body locally.
            logger.warning(f'[MOCK EMAIL SERVICE] Would send "{subject}" to {to}.\n{body}')
        return

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT or 587,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f'Sent "{subject}" email to {to}.')
    except Exception as e:
        logger.error(f'Failed to send "{subject}" email to {to}: {e}')
        raise EmailSendError("Couldn't send the email.") from e
