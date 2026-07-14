import logging

import pytest

from app.core.config import settings
from app.services import email as email_service


@pytest.mark.asyncio
async def test_dev_fallback_logs_body_when_smtp_not_configured(monkeypatch, caplog):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    with caplog.at_level(logging.WARNING):
        await email_service.send_email(to="student@example.com", subject="Verify your email", body="token-abc123")

    assert "token-abc123" in caplog.text
    assert "student@example.com" in caplog.text


@pytest.mark.asyncio
async def test_production_never_logs_the_token_when_smtp_not_configured(monkeypatch, caplog):
    """The actual vulnerability this file fixes: in production, with no real email service
    configured, the previous code path logged the raw reset/verification token - a working
    account-takeover credential - into the log stream. This must never happen again."""
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with caplog.at_level(logging.WARNING):
        await email_service.send_email(
            to="student@example.com", subject="Reset your password", body="secret-reset-token-xyz789"
        )

    assert "secret-reset-token-xyz789" not in caplog.text
    assert "not configured" in caplog.text.lower()


@pytest.mark.asyncio
async def test_sends_via_smtp_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "bot@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "EMAIL_FROM", "bot@example.com")

    sent = {}

    async def fake_send(message, **kwargs):
        sent["to"] = message["To"]
        sent["subject"] = message["Subject"]
        sent["body"] = message.get_content().strip()
        sent["hostname"] = kwargs["hostname"]

    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)

    await email_service.send_email(to="student@example.com", subject="Hello", body="World")

    assert sent["to"] == "student@example.com"
    assert sent["subject"] == "Hello"
    assert sent["body"] == "World"
    assert sent["hostname"] == "smtp.example.com"


@pytest.mark.asyncio
async def test_smtp_failure_raises_email_send_error(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "bot@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")

    async def failing_send(message, **kwargs):
        raise ConnectionError("SMTP server unreachable")

    monkeypatch.setattr(email_service.aiosmtplib, "send", failing_send)

    with pytest.raises(email_service.EmailSendError):
        await email_service.send_email(to="student@example.com", subject="Hello", body="World")
