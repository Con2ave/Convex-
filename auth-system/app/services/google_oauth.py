"""Verifies Google Identity Services ID tokens (the `credential` a Google Sign-In button hands
back). verify_google_id_token() is the entire public surface, same reasoning as
app.services.ai_client.generate_quiz - an isolated seam so it's the one thing tests monkeypatch,
and swapping verification strategy later doesn't touch any caller.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleTokenError(Exception):
    """Raised whenever a Google ID token can't be verified as authentic and current."""


@dataclass
class GoogleIdentity:
    google_id: str  # the token's `sub` claim - Google's stable, permanent user ID
    email: str
    email_verified: bool
    name: Optional[str] = None


def _verify_sync(credential: str) -> dict:
    """The actual blocking call (fetches/caches Google's public certs over HTTP) - isolated so
    asyncio.to_thread has a plain sync target."""
    return id_token.verify_oauth2_token(credential, Request(), audience=settings.GOOGLE_CLIENT_ID)


async def verify_google_id_token(credential: str) -> GoogleIdentity:
    """Verify a Google Identity Services ID token and return the identity it attests to.

    Raises GoogleTokenError on any verification failure - bad signature, expired, wrong
    audience, or wrong issuer are all covered by verify_oauth2_token's internal checks (it
    validates `iss` is accounts.google.com and `aud` matches settings.GOOGLE_CLIENT_ID).
    """
    try:
        idinfo = await asyncio.to_thread(_verify_sync, credential)
    except ValueError as e:
        logger.warning(f"Google ID token verification failed: {e}")
        raise GoogleTokenError("Invalid or expired Google credential.") from e

    return GoogleIdentity(
        google_id=idinfo["sub"],
        email=idinfo["email"],
        email_verified=bool(idinfo.get("email_verified", False)),
        name=idinfo.get("name"),
    )
