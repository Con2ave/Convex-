import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _parse(iso_str: str) -> datetime:
    """SQLite has no native tz-aware storage, so datetimes come back from the API as naive
    ISO strings even though they're UTC internally - same reason app code uses an _aware()
    helper throughout. Normalize here so arithmetic against tz-aware values works."""
    dt = datetime.fromisoformat(iso_str)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

TEST_USER_DATA = {
    "username": "subuser",
    "email": "subuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

OTHER_USER_DATA = {
    "username": "othersubuser",
    "email": "othersubuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}


async def _auth_headers(client: AsyncClient, user_data: dict = TEST_USER_DATA) -> dict:
    await client.post("/auth/register", json=user_data)
    login_resp = await client.post("/auth/login", data={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _enable_paystack(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_fake")


# ----------------- Plans -----------------

@pytest.mark.asyncio
async def test_plans_are_listed(client: AsyncClient):
    response = await client.get("/subscriptions/plans")
    assert response.status_code == 200
    plans = {p["plan"]: (p["ghs_amount"], p["duration_days"]) for p in response.json()}
    assert plans == {
        "monthly": (10, 30),
        "quarterly": (20, 90),
        "annual": (80, 365),
    }


# ----------------- Status -----------------

@pytest.mark.asyncio
async def test_status_starts_inactive(client: AsyncClient):
    headers = await _auth_headers(client)
    response = await client.get("/subscriptions/status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"is_active": False, "plan": None, "expires_at": None}


# ----------------- Initialize -----------------

@pytest.mark.asyncio
async def test_initialize_without_paystack_configured_returns_503(client: AsyncClient):
    headers = await _auth_headers(client)
    response = await client.post("/subscriptions/initialize", json={"plan": "monthly"}, headers=headers)
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_initialize_unknown_plan_rejected(client: AsyncClient, monkeypatch):
    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)
    response = await client.post("/subscriptions/initialize", json={"plan": "weekly"}, headers=headers)
    assert response.status_code == 422  # not one of the Literal plan values


@pytest.mark.asyncio
async def test_initialize_returns_checkout_url(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def fake_initialize(email, amount_ghs, reference, callback_url):
        assert amount_ghs == 10
        return {"authorization_url": "https://checkout.paystack.com/fake123", "reference": reference}

    monkeypatch.setattr(paystack_client, "initialize_transaction", fake_initialize)

    headers = await _auth_headers(client)
    response = await client.post("/subscriptions/initialize", json={"plan": "monthly"}, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["authorization_url"] == "https://checkout.paystack.com/fake123"
    assert data["reference"].startswith("sub-")


# ----------------- Verify -----------------

async def _initialize(client: AsyncClient, headers: dict, monkeypatch, plan: str = "monthly") -> str:
    from app.services import paystack_client

    async def fake_initialize(email, amount_ghs, reference, callback_url):
        return {"authorization_url": "https://checkout.paystack.com/fake", "reference": reference}

    monkeypatch.setattr(paystack_client, "initialize_transaction", fake_initialize)
    resp = await client.post("/subscriptions/initialize", json={"plan": plan}, headers=headers)
    return resp.json()["reference"]


@pytest.mark.asyncio
async def test_verify_success_activates_subscription(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)
    reference = await _initialize(client, headers, monkeypatch, "monthly")

    async def fake_verify(ref):
        assert ref == reference
        return "success"

    monkeypatch.setattr(paystack_client, "verify_transaction", fake_verify)

    before = datetime.now(timezone.utc)
    response = await client.post("/subscriptions/verify", json={"reference": reference}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["plan"] == "monthly"

    expires_at = _parse(data["expires_at"])
    # ~30 days out from roughly now.
    assert timedelta(days=29) < (expires_at - before) < timedelta(days=31)

    status_resp = await client.get("/subscriptions/status", headers=headers)
    status_data = status_resp.json()
    assert status_data["is_active"] is True
    assert status_data["plan"] == "monthly"


@pytest.mark.asyncio
async def test_verify_failed_payment_does_not_activate(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)
    reference = await _initialize(client, headers, monkeypatch)

    async def fake_verify(ref):
        return "abandoned"

    monkeypatch.setattr(paystack_client, "verify_transaction", fake_verify)

    response = await client.post("/subscriptions/verify", json={"reference": reference}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "failed"

    status_resp = await client.get("/subscriptions/status", headers=headers)
    assert status_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_verify_is_idempotent(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)
    reference = await _initialize(client, headers, monkeypatch)

    call_count = {"n": 0}

    async def fake_verify(ref):
        call_count["n"] += 1
        return "success"

    monkeypatch.setattr(paystack_client, "verify_transaction", fake_verify)

    first = await client.post("/subscriptions/verify", json={"reference": reference}, headers=headers)
    second = await client.post("/subscriptions/verify", json={"reference": reference}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["expires_at"] == second.json()["expires_at"]
    # The second call short-circuits on the already-active subscription without re-verifying.
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_verify_wrong_user_rejected(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client, TEST_USER_DATA)
    reference = await _initialize(client, headers, monkeypatch)

    other_headers = await _auth_headers(client, OTHER_USER_DATA)
    response = await client.post("/subscriptions/verify", json={"reference": reference}, headers=other_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resubscribing_while_active_extends_from_current_expiry(client: AsyncClient, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)

    async def fake_verify(ref):
        return "success"
    monkeypatch.setattr(paystack_client, "verify_transaction", fake_verify)

    ref1 = await _initialize(client, headers, monkeypatch, "monthly")
    resp1 = await client.post("/subscriptions/verify", json={"reference": ref1}, headers=headers)
    expires_1 = _parse(resp1.json()["expires_at"])

    ref2 = await _initialize(client, headers, monkeypatch, "monthly")
    resp2 = await client.post("/subscriptions/verify", json={"reference": ref2}, headers=headers)
    expires_2 = _parse(resp2.json()["expires_at"])

    # Second purchase should stack on top of the first, not restart from "now".
    assert (expires_2 - expires_1) > timedelta(days=29)


# ----------------- History -----------------

@pytest.mark.asyncio
async def test_history_lists_past_purchases(client: AsyncClient, monkeypatch):
    _enable_paystack(monkeypatch)
    headers = await _auth_headers(client)
    await _initialize(client, headers, monkeypatch, "annual")

    response = await client.get("/subscriptions/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["plan"] == "annual"
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_status_requires_auth(client: AsyncClient):
    response = await client.get("/subscriptions/status")
    assert response.status_code == 401
