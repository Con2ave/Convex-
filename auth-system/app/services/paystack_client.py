"""Thin client for Paystack - both directions of money flow:

- Transfers: pays Knowledge Point redemptions out to a student's Ghana mobile money wallet
  from the company's Paystack balance. Requires OTP confirmation (or business verification +
  the OTP-disable setting) before transfers actually complete - see app.services.reward.redeem().
- Transactions: charges a student's card/mobile money for a subscription. No verification wall;
  works on any account. See app.services.subscription.

In both directions, the initial API response only confirms the request was *accepted* - the
real outcome is confirmed either by polling a status endpoint or via webhook.
"""
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15.0

# Ghana mobile network names as they'll appear in our redemption form -> substrings to match
# against Paystack's GET /bank?currency=GHS&type=mobile_money listing (looked up and cached
# rather than hardcoded, since we don't have confirmed exact bank_code values for anything
# but MTN from public docs).
NETWORK_MATCH_HINTS = {
    "mtn": "mtn",
    "telecel": "vodafone",  # Telecel Ghana was formerly Vodafone Ghana; Paystack may list either name
    "airteltigo": "airteltigo",
}


class PaystackError(Exception):
    """Raised on any non-success response from the Paystack API."""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


# Ghana mobile money bank codes rarely change - cache the lookup for the life of the process.
_bank_code_cache: dict = {"codes": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 3600


async def _get_mobile_money_bank_code(network: str) -> str:
    hint = NETWORK_MATCH_HINTS.get(network.lower())
    if not hint:
        raise PaystackError(f"Unknown mobile money network: {network}")

    now = time.time()
    if not _bank_code_cache["codes"] or now - _bank_code_cache["fetched_at"] > _CACHE_TTL_SECONDS:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.PAYSTACK_BASE_URL}/bank",
                params={"currency": "GHS", "type": "mobile_money"},
                headers=_headers(),
            )
        if resp.status_code != 200:
            raise PaystackError(f"Failed to list mobile money networks: {resp.status_code} {resp.text}")
        _bank_code_cache["codes"] = resp.json().get("data", [])
        _bank_code_cache["fetched_at"] = now

    for entry in _bank_code_cache["codes"]:
        haystack = f"{entry.get('name', '')} {entry.get('slug', '')}".lower()
        if hint in haystack:
            return entry["code"]

    raise PaystackError(f"Couldn't find a Paystack bank_code for network '{network}'.")


def _normalize_phone(phone: str) -> str:
    """Paystack expects a local-format Ghana number (e.g. 0241234567), not the +233 form."""
    digits = "".join(ch for ch in phone.strip() if ch.isdigit())
    if digits.startswith("233"):
        digits = "0" + digits[3:]
    return digits


async def create_transfer_recipient(recipient_name: str, phone: str, network: str) -> str:
    """Creates (or effectively re-creates - Paystack dedupes by account_number+bank_code)
    a transfer recipient and returns its recipient_code, needed to initiate a transfer."""
    bank_code = await _get_mobile_money_bank_code(network)

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.PAYSTACK_BASE_URL}/transferrecipient",
            json={
                "type": "mobile_money",
                "name": recipient_name,
                "account_number": _normalize_phone(phone),
                "bank_code": bank_code,
                "currency": "GHS",
            },
            headers=_headers(),
        )

    if resp.status_code not in (200, 201):
        raise PaystackError(f"Failed to create transfer recipient: {resp.status_code} {resp.text}")

    data = resp.json().get("data", {})
    recipient_code = data.get("recipient_code")
    if not recipient_code:
        raise PaystackError(f"Paystack didn't return a recipient_code: {resp.text}")
    return recipient_code


async def initiate_transfer(recipient_code: str, amount_ghs: int, reason: str, reference: str) -> dict:
    """Initiates the payout. Returns {"transfer_code": str, "status": str}.
    A "success" status here (common in test mode) means it's actually done; "pending" means
    the real outcome will only be known later via webhook or a status check."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.PAYSTACK_BASE_URL}/transfer",
            json={
                "source": "balance",
                "amount": amount_ghs * 100,  # Paystack wants the smallest currency unit (pesewas)
                "recipient": recipient_code,
                "reason": reason,
                "reference": reference,
            },
            headers=_headers(),
        )

    if resp.status_code not in (200, 201):
        raise PaystackError(f"Transfer request rejected: {resp.status_code} {resp.text}")

    data = resp.json().get("data", {})
    transfer_code = data.get("transfer_code")
    transfer_status = data.get("status", "pending")
    if not transfer_code:
        raise PaystackError(f"Paystack didn't return a transfer_code: {resp.text}")

    logger.info(f"Paystack transfer initiated: transfer_code={transfer_code}, status={transfer_status}")
    return {"transfer_code": transfer_code, "status": transfer_status}


async def get_transfer_status(transfer_code: str) -> str:
    """Returns Paystack's status string: pending / success / failed / reversed, etc."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.PAYSTACK_BASE_URL}/transfer/{transfer_code}",
            headers=_headers(),
        )

    if resp.status_code != 200:
        raise PaystackError(f"Failed to check transfer status: {resp.status_code} {resp.text}")

    return resp.json().get("data", {}).get("status", "pending")


# ----------------- Transactions (Collections) - subscription payments -----------------
# The other direction of money flow: charging a student's card/mobile money to pay ConVex,
# not paying a student out. This is Paystack's flagship, most-used API - no OTP/verification
# wall like Transfers has, works immediately on any account including unverified ones.

async def initialize_transaction(email: str, amount_ghs: int, reference: str, callback_url: str) -> dict:
    """Starts a payment. Returns {"authorization_url": str, "reference": str} - redirect the
    browser to authorization_url to let the student pay; Paystack redirects back to
    callback_url?reference=... afterward, which verify_transaction() then confirms server-side."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
            json={
                "email": email,
                "amount": amount_ghs * 100,  # smallest currency unit (pesewas)
                "currency": "GHS",
                "reference": reference,
                "callback_url": callback_url,
            },
            headers=_headers(),
        )

    if resp.status_code not in (200, 201):
        raise PaystackError(f"Failed to initialize transaction: {resp.status_code} {resp.text}")

    data = resp.json().get("data", {})
    authorization_url = data.get("authorization_url")
    if not authorization_url:
        raise PaystackError(f"Paystack didn't return an authorization_url: {resp.text}")
    return {"authorization_url": authorization_url, "reference": data.get("reference", reference)}


async def verify_transaction(reference: str) -> str:
    """Returns Paystack's transaction status: success / failed / abandoned. Always check this
    server-side before trusting a payment succeeded - never trust the client's word for it."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=_headers(),
        )

    if resp.status_code != 200:
        raise PaystackError(f"Failed to verify transaction: {resp.status_code} {resp.text}")

    return resp.json().get("data", {}).get("status", "abandoned")
