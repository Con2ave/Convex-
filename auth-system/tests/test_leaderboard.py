import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import RewardLedgerEntry
from app.models.study_session import StudySession
from app.models.user import User

TEST_USER_DATA = {
    "username": "leaderuser",
    "email": "leaderuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

OTHER_USER_DATA = {
    "username": "boardrunnerup",
    "email": "boardrunnerup@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

THIRD_USER_DATA = {
    "username": "aaaboardthird",
    "email": "aaaboardthird@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}


async def _auth_headers(client: AsyncClient, user_data: dict = TEST_USER_DATA) -> dict:
    """Register (idempotently) and log in a user, returning bearer auth headers. No subscription
    seeding needed - the leaderboard doesn't touch the paywall/redemption path at all."""
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


async def _seed_balance(db_session: AsyncSession, user_id: int, points: int) -> None:
    db_session.add(RewardLedgerEntry(user_id=user_id, points=points, reason="session_verified"))
    await db_session.commit()


async def _seed_completed_day(db_session: AsyncSession, user_id: int, ended_at: datetime) -> None:
    """Directly insert a completed session on a given day, purely as a streak marker - its own
    KP doesn't matter, only that it makes that calendar day count toward the streak."""
    session = StudySession(
        user_id=user_id,
        status="completed",
        started_at=ended_at - timedelta(minutes=30),
        ended_at=ended_at,
        last_activity_at=ended_at,
        accumulated_seconds=1800,
        verified_minutes=15
    )
    db_session.add(session)
    await db_session.commit()


# ----------------- Points leaderboard -----------------

@pytest.mark.asyncio
async def test_empty_leaderboards_return_empty_list(client: AsyncClient):
    headers = await _auth_headers(client)

    points_resp = await client.get("/leaderboard/points", headers=headers)
    streaks_resp = await client.get("/leaderboard/streaks", headers=headers)

    assert points_resp.json() == []
    assert streaks_resp.json() == []


@pytest.mark.asyncio
async def test_points_leaderboard_descending_order_and_shape(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    other_headers = await _auth_headers(client, OTHER_USER_DATA)

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 500)
    await _seed_balance(db_session, other_id, 1000)

    response = await client.get("/leaderboard/points", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert [e["username"] for e in data] == [OTHER_USER_DATA["username"], TEST_USER_DATA["username"]]
    assert [e["points"] for e in data] == [1000, 500]
    # Exact shape - no PII leak (no id/email/role).
    for entry in data:
        assert set(entry.keys()) == {"username", "points"}


@pytest.mark.asyncio
async def test_points_leaderboard_ties_broken_by_username(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    other_headers = await _auth_headers(client, OTHER_USER_DATA)

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 500)
    await _seed_balance(db_session, other_id, 500)

    response = await client.get("/leaderboard/points", headers=headers)
    data = response.json()
    usernames = [e["username"] for e in data]
    # "boardrunnerup" < "leaderuser" alphabetically.
    assert usernames == sorted([OTHER_USER_DATA["username"], TEST_USER_DATA["username"]])


@pytest.mark.asyncio
async def test_points_leaderboard_excludes_users_with_no_activity(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    await _auth_headers(client, OTHER_USER_DATA)  # registered, never earns anything

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 100)

    response = await client.get("/leaderboard/points", headers=headers)
    data = response.json()
    assert [e["username"] for e in data] == [TEST_USER_DATA["username"]]


# ----------------- Streak leaderboard -----------------

@pytest.mark.asyncio
async def test_streak_leaderboard_descending_order_and_shape(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    await _auth_headers(client, OTHER_USER_DATA)

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])

    now = datetime.now(timezone.utc)
    # user: 5 consecutive days including today.
    for days_ago in range(5):
        await _seed_completed_day(db_session, user_id, now - timedelta(days=days_ago))
    # other: 2 consecutive days including today.
    for days_ago in range(2):
        await _seed_completed_day(db_session, other_id, now - timedelta(days=days_ago))

    response = await client.get("/leaderboard/streaks", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert [e["username"] for e in data] == [TEST_USER_DATA["username"], OTHER_USER_DATA["username"]]
    assert [e["streak_days"] for e in data] == [5, 2]
    for entry in data:
        assert set(entry.keys()) == {"username", "streak_days"}


@pytest.mark.asyncio
async def test_streak_broken_by_gap_is_capped_not_summed(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    now = datetime.now(timezone.utc)

    # Days {0, 1} consecutive, then a gap at day 2, then {3, 4} - streak must stop at the gap.
    for days_ago in (0, 1, 3, 4):
        await _seed_completed_day(db_session, user_id, now - timedelta(days=days_ago))

    response = await client.get("/leaderboard/streaks", headers=headers)
    data = response.json()
    assert data == [{"username": TEST_USER_DATA["username"], "streak_days": 2}]


@pytest.mark.asyncio
async def test_streak_leaderboard_excludes_users_whose_streak_is_broken(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    other_headers = await _auth_headers(client, OTHER_USER_DATA)

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])

    now = datetime.now(timezone.utc)
    await _seed_completed_day(db_session, user_id, now)  # active today - streak alive
    await _seed_completed_day(db_session, other_id, now - timedelta(days=5))  # stale - streak is 0

    response = await client.get("/leaderboard/streaks", headers=headers)
    data = response.json()
    assert [e["username"] for e in data] == [TEST_USER_DATA["username"]]


@pytest.mark.asyncio
async def test_streak_leaderboard_ties_broken_by_username(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    await _auth_headers(client, OTHER_USER_DATA)

    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])
    now = datetime.now(timezone.utc)

    for uid in (user_id, other_id):
        await _seed_completed_day(db_session, uid, now)
        await _seed_completed_day(db_session, uid, now - timedelta(days=1))

    response = await client.get("/leaderboard/streaks", headers=headers)
    data = response.json()
    usernames = [e["username"] for e in data]
    assert usernames == sorted([OTHER_USER_DATA["username"], TEST_USER_DATA["username"]])
    assert all(e["streak_days"] == 2 for e in data)


# ----------------- Shared behavior -----------------

@pytest.mark.asyncio
async def test_leaderboards_capped_at_fifty_entries(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    now = datetime.now(timezone.utc)

    for i in range(55):
        user_data = {
            "username": f"boarduser{i}",
            "email": f"boarduser{i}@example.com",
            "password": "SecurePassword123!",
            "password_confirm": "SecurePassword123!",
        }
        await client.post("/auth/register", json=user_data)
        user_id = await _get_user_id(db_session, user_data["username"])
        await _seed_balance(db_session, user_id, 100 + i)
        await _seed_completed_day(db_session, user_id, now)

    points_resp = await client.get("/leaderboard/points", headers=headers)
    streaks_resp = await client.get("/leaderboard/streaks", headers=headers)

    assert len(points_resp.json()) == 50
    assert len(streaks_resp.json()) == 50


@pytest.mark.asyncio
async def test_leaderboards_require_auth(client: AsyncClient):
    points_resp = await client.get("/leaderboard/points")
    streaks_resp = await client.get("/leaderboard/streaks")
    assert points_resp.status_code == 401
    assert streaks_resp.status_code == 401


@pytest.mark.asyncio
async def test_leaderboard_shows_other_users_data(client: AsyncClient, db_session: AsyncSession):
    """The actual point of the feature: user A can see user B's ranking despite never having
    interacted with them - not just an incidental side effect of the ordering tests above."""
    headers = await _auth_headers(client)
    other_headers = await _auth_headers(client, OTHER_USER_DATA)

    other_id = await _get_user_id(db_session, OTHER_USER_DATA["username"])
    await _seed_balance(db_session, other_id, 42)
    await _seed_completed_day(db_session, other_id, datetime.now(timezone.utc))

    points_resp = await client.get("/leaderboard/points", headers=headers)
    streaks_resp = await client.get("/leaderboard/streaks", headers=headers)

    assert OTHER_USER_DATA["username"] in [e["username"] for e in points_resp.json()]
    assert OTHER_USER_DATA["username"] in [e["username"] for e in streaks_resp.json()]
