import asyncio
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_session import StudySession, SessionCheck
from app.models.reward import RewardLedgerEntry
from app.models.subscription import Subscription
from app.models.user import User
from app.services import reward as reward_service
from app.services.reward import _streak_multiplier

TEST_USER_DATA = {
    "username": "rewarduser",
    "email": "rewarduser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

OTHER_USER_DATA = {
    "username": "otherrewarduser",
    "email": "otherrewarduser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}


async def _auth_headers(client: AsyncClient, db_session: AsyncSession, user_data: dict = TEST_USER_DATA) -> dict:
    """Register (idempotently) and log in a user, returning bearer auth headers.
    Also seeds an active subscription so the paywall on session start doesn't block these tests -
    subscription behavior itself is covered separately in test_subscriptions.py / test_paywall.py."""
    await client.post("/auth/register", json=user_data)
    login_resp = await client.post("/auth/login", data={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    token = login_resp.json()["access_token"]

    user_id = await _get_user_id(db_session, user_data["username"])
    db_session.add(Subscription(
        user_id=user_id,
        plan="monthly",
        ghs_amount=10,
        status="active",
        provider_ref=f"test-sub-{uuid.uuid4().hex}",
        started_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    await db_session.commit()

    return {"Authorization": f"Bearer {token}"}


async def _get_user_id(db_session: AsyncSession, username: str) -> int:
    result = await db_session.execute(select(User).where(User.username == username))
    return result.scalar_one().id


async def _rewind(db_session: AsyncSession, session_id: int, **fields):
    """Directly backdate/patch a StudySession row to simulate elapsed time in tests."""
    await db_session.execute(update(StudySession).where(StudySession.id == session_id).values(**fields))
    await db_session.commit()


async def _complete_session(client: AsyncClient, db_session: AsyncSession, headers: dict, minutes: int) -> int:
    """Start, backdate, and end a session so it lands as 'completed' with the given verified minutes.
    Stay at or under the 180 min/day cap (see test_study_sessions.py) unless testing the cap itself."""
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]
    await _rewind(db_session, session_id, accumulated_seconds=minutes * 60)
    await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Worked through past-paper questions for two subjects."},
        headers=headers
    )
    return session_id


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


async def _attach_check(db_session: AsyncSession, session_id: int, passed: bool) -> None:
    now = datetime.now(timezone.utc)
    check = SessionCheck(
        session_id=session_id,
        check_type="attention",
        prompt="Still there?",
        triggered_at=now,
        expires_at=now + timedelta(seconds=15),
        responded_at=now,
        passed=passed
    )
    db_session.add(check)
    await db_session.commit()


# ----------------- Earning: Knowledge Points -----------------
# 10 KP / 30-min study block, +10 perfect-session bonus, +2 first-session-of-day bonus,
# all scaled by the streak multiplier (app.services.reward.award_session_points).

@pytest.mark.asyncio
async def test_balance_starts_at_zero(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    response = await client.get("/rewards/balance", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"points": 0}


@pytest.mark.asyncio
async def test_base_kp_plus_daily_bonus_on_first_session(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    # 90 min = 3 blocks = 30 KP base. No checks -> not "perfect". First session today -> +2.
    # Streak is 1 (only today) -> 1.0x multiplier. Expect floor((30 + 2) * 1.0) = 32.
    session_id = await _complete_session(client, db_session, headers, minutes=90)

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 32}

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    entries = ledger_resp.json()
    assert len(entries) == 1
    assert entries[0]["points"] == 32
    assert entries[0]["reason"] == "session_verified"
    assert entries[0]["session_id"] == session_id


@pytest.mark.asyncio
async def test_partial_block_minutes_are_not_credited(client: AsyncClient, db_session: AsyncSession):
    # 40 min is only 1 full 30-min block - the remaining 10 min isn't worth a partial KP.
    headers = await _auth_headers(client, db_session)
    await _complete_session(client, db_session, headers, minutes=40)
    # base = 1 block * 10 = 10, + first-session bonus 2 = 12, streak 1x -> 12.
    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 12}


@pytest.mark.asyncio
async def test_perfect_session_bonus_only_on_answered_checks(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)

    # Session A: consumes the daily-first-session bonus, no checks attached.
    session_a = await _complete_session(client, db_session, headers, minutes=30)  # 10 + 2 = 12 KP

    # Session B: same day (no daily bonus), one passed check attached -> perfect.
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_b = start_resp.json()["id"]
    await _attach_check(db_session, session_b, passed=True)
    await _rewind(db_session, session_b, accumulated_seconds=30 * 60)
    await client.post(
        f"/study-sessions/{session_b}/end",
        json={"summary_text": "Reviewed the same material again from a different angle."},
        headers=headers
    )
    # base 10 + perfect bonus 10 (no daily bonus, already used) = 20, streak still 1x -> 20.

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 12 + 20}

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    by_session = {e["session_id"]: e["points"] for e in ledger_resp.json()}
    assert by_session[session_a] == 12
    assert by_session[session_b] == 20


@pytest.mark.asyncio
async def test_failed_check_breaks_perfect_bonus(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]
    await _attach_check(db_session, session_id, passed=False)
    await _rewind(db_session, session_id, accumulated_seconds=30 * 60)
    await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Got distracted partway through but finished the chapter."},
        headers=headers
    )
    # base 10 + no perfect bonus (one check failed) + daily bonus 2 = 12.
    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 12}


@pytest.mark.asyncio
async def test_streak_extends_multiplier_across_real_days(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])

    # Seed 6 prior consecutive days of study history (streak markers only).
    today = datetime.now(timezone.utc)
    for days_ago in range(1, 7):
        await _seed_completed_day(db_session, user_id, today - timedelta(days=days_ago))

    # Completing a session today makes it a 7-day streak -> 1.2x multiplier.
    await _complete_session(client, db_session, headers, minutes=60)  # base 20 + daily bonus 2 = 22
    expected = (20 + 2) * 1.2  # 26.4 -> floors to 26

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": int(expected)}


@pytest.mark.parametrize("streak_days,expected_multiplier", [
    (1, 1.0), (6, 1.0),
    (7, 1.2), (13, 1.2),
    (14, 1.5), (29, 1.5),
    (30, 2.0), (59, 2.0),
    (60, 2.5), (365, 2.5),  # capped - never exceeds 2.5x no matter how long the streak
])
def test_streak_multiplier_table_is_capped(streak_days, expected_multiplier):
    from decimal import Decimal
    assert _streak_multiplier(streak_days) == Decimal(str(expected_multiplier))


@pytest.mark.asyncio
async def test_open_session_does_not_count_toward_balance(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    await client.post("/study-sessions/start", json={"subject_tag": "Physics"}, headers=headers)

    response = await client.get("/rewards/balance", headers=headers)
    assert response.json() == {"points": 0}


@pytest.mark.asyncio
async def test_flagged_session_awards_no_points(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Force the session to look abandoned so it gets auto-flagged (mirrors test_study_sessions.py).
    await _rewind(db_session, session_id, last_activity_at=datetime.now(timezone.utc) - timedelta(seconds=1300))
    await client.get(f"/study-sessions/{session_id}", headers=headers)  # triggers lazy stale-flagging

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 0}
    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    assert ledger_resp.json() == []


@pytest.mark.asyncio
async def test_balance_is_per_user(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session, TEST_USER_DATA)
    await _complete_session(client, db_session, headers, minutes=90)

    other_headers = await _auth_headers(client, db_session, OTHER_USER_DATA)
    response = await client.get("/rewards/balance", headers=other_headers)
    assert response.json() == {"points": 0}


# ----------------- Redemption: fixed MoMo cash tiers -----------------

async def _seed_balance(db_session: AsyncSession, user_id: int, points: int) -> None:
    db_session.add(RewardLedgerEntry(user_id=user_id, points=points, reason="session_verified"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_redemption_lock_serializes_same_user_concurrent_calls():
    """Directly exercises the per-user lock reward.redeem() holds for its full duration - this
    is what prevents two concurrent redemption requests for the same user from both reading the
    same pre-deduction balance and both passing the affordability check (double-spend)."""
    user_id = 900001
    order = []

    async def hold_lock():
        async with reward_service._redemption_locks[user_id]:
            order.append("first-acquired")
            await asyncio.sleep(0.05)
            order.append("first-released")

    async def try_acquire():
        await asyncio.sleep(0.01)  # let the first task acquire first
        async with reward_service._redemption_locks[user_id]:
            order.append("second-acquired")

    await asyncio.gather(hold_lock(), try_acquire())

    assert order == ["first-acquired", "first-released", "second-acquired"]


@pytest.mark.asyncio
async def test_redemption_lock_is_per_user_not_global():
    """Different users' redemptions must not block each other."""
    lock_a = reward_service._redemption_locks[900002]
    lock_b = reward_service._redemption_locks[900003]
    assert lock_a is not lock_b


@pytest.mark.asyncio
async def test_redemption_tiers_are_listed(client: AsyncClient):
    response = await client.get("/rewards/redemption-tiers")
    assert response.status_code == 200
    tiers = {t["ghs_amount"]: t["kp_cost"] for t in response.json()}
    assert tiers == {1: 300, 2: 600, 5: 1500, 10: 3500}


@pytest.mark.asyncio
async def test_redeem_invalid_tier_rejected(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 5000)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 3, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 400
    assert "isn't an available redemption tier" in response.json()["detail"]


@pytest.mark.asyncio
async def test_redeem_insufficient_balance_rejected(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 100)  # not enough for even the cheapest tier (300 KP)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 400
    assert "Insufficient balance" in response.json()["detail"]


@pytest.mark.asyncio
async def test_redeem_success_deducts_balance_and_logs_redemption(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 1500)  # exactly the GHS 5 tier

    redeem_resp = await client.post(
        "/rewards/redeem", json={"ghs_amount": 5, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert redeem_resp.status_code == 201
    data = redeem_resp.json()
    assert data["status"] == "completed"
    assert data["points_spent"] == 1500
    assert data["ghs_amount"] == 5
    assert data["reward_type"] == "momo"
    assert data["provider_ref"] is not None
    assert data["recipient_phone"] == "+233241234567"
    assert data["network"] == "mtn"

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 0}

    redemptions_resp = await client.get("/rewards/redemptions", headers=headers)
    redemptions = redemptions_resp.json()
    assert len(redemptions) == 1
    assert redemptions[0]["id"] == data["id"]

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    entries = ledger_resp.json()
    assert len(entries) == 2
    assert entries[0]["reason"] == "redemption:momo"
    assert entries[0]["points"] == -1500


@pytest.mark.asyncio
async def test_redeem_requires_auth(client: AsyncClient):
    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}
    )
    assert response.status_code == 401


# ----------------- Real Paystack payout branch (mocked HTTP layer) -----------------
# These exercise app.services.reward's real-payout branch without touching the network -
# app.services.paystack_client itself is trusted to be correct at the wire level once real
# sandbox credentials are available; here we only verify reward.py's orchestration around it
# (status branching, refund-on-failure).

def _enable_paystack(monkeypatch):
    from app.core.config import settings
    from app.services import reward as reward_service
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(reward_service, "TRANSFER_STATUS_POLL_DELAY_SECONDS", 0)


@pytest.mark.asyncio
async def test_real_payout_success_immediate(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def fake_create_recipient(recipient_name, phone, network):
        return "RCP_fake123"

    async def fake_initiate_transfer(recipient_code, amount_ghs, reason, reference):
        return {"transfer_code": "TRF_fake123", "status": "success"}  # test-mode transfers resolve immediately

    monkeypatch.setattr(paystack_client, "create_transfer_recipient", fake_create_recipient)
    monkeypatch.setattr(paystack_client, "initiate_transfer", fake_initiate_transfer)

    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 300)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    assert data["provider_ref"] == "TRF_fake123"

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 0}


@pytest.mark.asyncio
async def test_real_payout_resolves_after_polling(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def fake_create_recipient(recipient_name, phone, network):
        return "RCP_fake456"

    async def fake_initiate_transfer(recipient_code, amount_ghs, reason, reference):
        return {"transfer_code": "TRF_fake456", "status": "pending"}  # needs a status check to resolve

    async def fake_status(transfer_code):
        return "success"

    monkeypatch.setattr(paystack_client, "create_transfer_recipient", fake_create_recipient)
    monkeypatch.setattr(paystack_client, "initiate_transfer", fake_initiate_transfer)
    monkeypatch.setattr(paystack_client, "get_transfer_status", fake_status)

    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 300)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_real_payout_failure_refunds_points(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def fake_create_recipient(recipient_name, phone, network):
        return "RCP_fake789"

    async def fake_initiate_transfer(recipient_code, amount_ghs, reason, reference):
        return {"transfer_code": "TRF_fake789", "status": "failed"}

    monkeypatch.setattr(paystack_client, "create_transfer_recipient", fake_create_recipient)
    monkeypatch.setattr(paystack_client, "initiate_transfer", fake_initiate_transfer)

    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 300)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "failed"

    # The KP was never actually spent - Paystack rejected the payout, so it comes back.
    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 300}

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    reasons = [e["reason"] for e in ledger_resp.json()]
    assert reasons.count("redemption:momo") == 1
    assert reasons.count("redemption_refund:momo") == 1


@pytest.mark.asyncio
async def test_real_payout_pending_after_poll_timeout(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def fake_create_recipient(recipient_name, phone, network):
        return "RCP_fakeabc"

    async def fake_initiate_transfer(recipient_code, amount_ghs, reason, reference):
        return {"transfer_code": "TRF_fakeabc", "status": "pending"}

    async def fake_status(transfer_code):
        return "pending"  # never resolves within the poll window

    monkeypatch.setattr(paystack_client, "create_transfer_recipient", fake_create_recipient)
    monkeypatch.setattr(paystack_client, "initiate_transfer", fake_initiate_transfer)
    monkeypatch.setattr(paystack_client, "get_transfer_status", fake_status)

    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 300)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"

    # KP stays deducted while genuinely pending - it hasn't failed, just not confirmed yet.
    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 0}


@pytest.mark.asyncio
async def test_real_payout_request_error_marks_failed_and_refunds(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    from app.services import paystack_client

    _enable_paystack(monkeypatch)

    async def failing_create_recipient(recipient_name, phone, network):
        raise paystack_client.PaystackError("simulated network failure")

    monkeypatch.setattr(paystack_client, "create_transfer_recipient", failing_create_recipient)

    headers = await _auth_headers(client, db_session)
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])
    await _seed_balance(db_session, user_id, 300)

    response = await client.post(
        "/rewards/redeem", json={"ghs_amount": 1, "recipient_phone": "+233241234567", "network": "mtn"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "failed"

    balance_resp = await client.get("/rewards/balance", headers=headers)
    assert balance_resp.json() == {"points": 300}
