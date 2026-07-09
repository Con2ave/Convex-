import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models.reward import RewardLedgerEntry
from app.models.study_session import StudySession
from app.models.subscription import Subscription
from app.models.user import User

TEST_USER_DATA = {
    "username": "paywalluser",
    "email": "paywalluser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

TEST_ADMIN_DATA = {
    "username": "paywalladmin",
    "email": "paywalladmin@example.com",
    "password": "SecurePassword123!"
}

REDEEM_PAYLOAD = {"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}


async def _register_and_login(client: AsyncClient, user_data: dict = TEST_USER_DATA) -> dict:
    await client.post("/auth/register", json=user_data)
    login_resp = await client.post("/auth/login", data={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _get_user_id(db_session: AsyncSession, username: str) -> int:
    result = await db_session.execute(select(User).where(User.username == username))
    return result.scalar_one().id


async def _seed_admin(db_session: AsyncSession) -> User:
    admin = User(
        username=TEST_ADMIN_DATA["username"],
        email=TEST_ADMIN_DATA["email"],
        hashed_password=security.get_password_hash(TEST_ADMIN_DATA["password"]),
        role="admin",
        is_active=True,
        is_verified=True
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


async def _admin_headers(client: AsyncClient, db_session: AsyncSession) -> dict:
    await _seed_admin(db_session)
    login_resp = await client.post("/auth/login", data={
        "username": TEST_ADMIN_DATA["username"],
        "password": TEST_ADMIN_DATA["password"]
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_subscription(db_session: AsyncSession, user_id: int, status: str, expires_at: datetime) -> None:
    db_session.add(Subscription(
        user_id=user_id,
        plan="monthly",
        ghs_amount=10,
        status=status,
        provider_ref=f"test-sub-{user_id}-{status}-{expires_at.timestamp()}",
        started_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    ))
    await db_session.commit()


async def _seed_balance(db_session: AsyncSession, user_id: int, points: int) -> None:
    db_session.add(RewardLedgerEntry(user_id=user_id, points=points, reason="session_verified"))
    await db_session.commit()


# ----------------- Studying stays free regardless of subscription -----------------

@pytest.mark.asyncio
async def test_unsubscribed_user_can_start_and_study(client: AsyncClient):
    """Declining to subscribe never blocks core app usage - only cashing KP out for money."""
    headers = await _register_and_login(client)
    response = await client.post("/study-sessions/start", json={}, headers=headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_unsubscribed_user_earns_knowledge_points(client: AsyncClient, db_session: AsyncSession):
    headers = await _register_and_login(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    await db_session.execute(
        update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=30 * 60)
    )
    await db_session.commit()

    await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Studied for half an hour without a subscription."},
        headers=headers
    )

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json()["points"] > 0


# ----------------- Redeeming KP for cash requires an active subscription -----------------

@pytest.mark.asyncio
async def test_unsubscribed_user_cannot_redeem(client: AsyncClient, db_session: AsyncSession):
    headers = await _register_and_login(client)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 5000)

    response = await client.post("/rewards/redeem", json=REDEEM_PAYLOAD, headers=headers)
    assert response.status_code == 402
    assert "subscription" in response.json()["detail"].lower()

    # The balance is untouched - declining to subscribe doesn't cost KP, it just can't be cashed out.
    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json()["points"] == 5000


@pytest.mark.asyncio
async def test_user_with_expired_subscription_cannot_redeem(client: AsyncClient, db_session: AsyncSession):
    headers = await _register_and_login(client)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 5000)
    await _seed_subscription(
        db_session, user_id, status="active", expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )

    response = await client.post("/rewards/redeem", json=REDEEM_PAYLOAD, headers=headers)
    assert response.status_code == 402


@pytest.mark.asyncio
async def test_subscribed_user_can_redeem(client: AsyncClient, db_session: AsyncSession):
    headers = await _register_and_login(client)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 5000)
    await _seed_subscription(
        db_session, user_id, status="active", expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )

    response = await client.post("/rewards/redeem", json=REDEEM_PAYLOAD, headers=headers)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_admin_bypasses_subscription_requirement_for_redeem(client: AsyncClient, db_session: AsyncSession):
    headers = await _admin_headers(client, db_session)
    admin_id = await _get_user_id(db_session, TEST_ADMIN_DATA["username"])
    await _seed_balance(db_session, admin_id, 5000)

    response = await client.post("/rewards/redeem", json=REDEEM_PAYLOAD, headers=headers)
    assert response.status_code == 201
