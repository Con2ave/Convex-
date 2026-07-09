import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_session import StudySession, SessionCheck, SessionEvent
from app.models.user import User

TEST_USER_DATA = {
    "username": "studyuser",
    "email": "studyuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

OTHER_USER_DATA = {
    "username": "otherstudyuser",
    "email": "otherstudyuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}


async def _auth_headers(client: AsyncClient, user_data: dict = TEST_USER_DATA) -> dict:
    """Register (idempotently) and log in a user, returning bearer auth headers."""
    await client.post("/auth/register", json=user_data)
    login_resp = await client.post("/auth/login", data={
        "username": user_data["username"],
        "password": user_data["password"]
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _rewind(db_session: AsyncSession, session_id: int, **fields):
    """Directly backdate/patch a StudySession row to simulate elapsed time in tests."""
    await db_session.execute(update(StudySession).where(StudySession.id == session_id).values(**fields))
    await db_session.commit()


# ----------------- Start Session Tests -----------------

@pytest.mark.asyncio
async def test_start_session_success(client: AsyncClient):
    headers = await _auth_headers(client)
    response = await client.post("/study-sessions/start", json={"subject_tag": "Biology"}, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "active"
    assert data["subject_tag"] == "Biology"
    assert data["accumulated_seconds"] == 0
    assert data["verified_minutes"] == 0


@pytest.mark.asyncio
async def test_cannot_start_second_open_session(client: AsyncClient):
    headers = await _auth_headers(client)
    await client.post("/study-sessions/start", json={}, headers=headers)

    response = await client.post("/study-sessions/start", json={}, headers=headers)
    assert response.status_code == 400
    assert "already have an active study session" in response.json()["detail"]


@pytest.mark.asyncio
async def test_start_session_requires_auth(client: AsyncClient):
    response = await client.post("/study-sessions/start", json={})
    assert response.status_code == 401


# ----------------- Heartbeat / Timer Tests -----------------

@pytest.mark.asyncio
async def test_heartbeat_accumulates_elapsed_time(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Simulate 10 real seconds having passed since the last ping.
    await _rewind(db_session, session_id, last_activity_at=datetime.now(timezone.utc) - timedelta(seconds=10))

    response = await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["accumulated_seconds"] >= 9


@pytest.mark.asyncio
async def test_heartbeat_does_not_credit_large_gaps(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Gap far exceeds the heartbeat grace window (default 45s) but stays under the stale timeout.
    await _rewind(db_session, session_id, last_activity_at=datetime.now(timezone.utc) - timedelta(seconds=300))

    response = await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)
    assert response.status_code == 200
    assert response.json()["accumulated_seconds"] == 0

    result = await db_session.execute(select(SessionEvent).where(SessionEvent.session_id == session_id))
    events = result.scalars().all()
    assert any(e.event_type == "gap" for e in events)


@pytest.mark.asyncio
async def test_stale_session_is_auto_flagged(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Beyond the stale timeout (default 1200s) with no heartbeat at all.
    await _rewind(db_session, session_id, last_activity_at=datetime.now(timezone.utc) - timedelta(seconds=1300))

    response = await client.get(f"/study-sessions/{session_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "flagged"
    assert data["verified_minutes"] == 0


# ----------------- Pause / Resume Tests -----------------

@pytest.mark.asyncio
async def test_pause_and_resume_flow(client: AsyncClient):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    pause_resp = await client.post(f"/study-sessions/{session_id}/pause", headers=headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    # Pausing an already-paused session is rejected.
    second_pause = await client.post(f"/study-sessions/{session_id}/pause", headers=headers)
    assert second_pause.status_code == 400

    resume_resp = await client.post(f"/study-sessions/{session_id}/resume", headers=headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "active"


# ----------------- Anti-cheat Check Tests -----------------

@pytest.mark.asyncio
async def test_due_check_is_issued_and_can_be_answered(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Force the next check to be due immediately.
    await _rewind(db_session, session_id, next_check_at=datetime.now(timezone.utc) - timedelta(seconds=1))

    hb_resp = await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)
    assert hb_resp.status_code == 200
    pending = hb_resp.json()["pending_check"]
    assert pending is not None
    assert pending["check_type"] in ("attention", "recall")
    assert pending["passed"] is None

    respond_resp = await client.post(
        f"/study-sessions/{session_id}/checks/{pending['id']}/respond",
        json={"response": "ok"},
        headers=headers
    )
    assert respond_resp.status_code == 200
    assert respond_resp.json()["passed"] is True

    # Answering an already-resolved check is rejected.
    second_respond = await client.post(
        f"/study-sessions/{session_id}/checks/{pending['id']}/respond",
        json={"response": "ok"},
        headers=headers
    )
    assert second_respond.status_code == 400


@pytest.mark.asyncio
async def test_session_auto_flagged_after_repeated_missed_checks(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Default STUDY_CHECK_MAX_FAILURES is 2 - miss two checks in a row via heartbeats.
    for _ in range(2):
        await _rewind(db_session, session_id, next_check_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)

        result = await db_session.execute(
            select(SessionCheck).where(SessionCheck.session_id == session_id, SessionCheck.passed.is_(None))
        )
        pending_check = result.scalars().first()
        assert pending_check is not None
        # Force this check's window to have already closed, then let the next heartbeat resolve it.
        await _rewind(db_session, session_id, next_check_at=datetime.now(timezone.utc) + timedelta(hours=1))
        await db_session.execute(
            update(SessionCheck).where(SessionCheck.id == pending_check.id).values(
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
            )
        )
        await db_session.commit()
        await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)

    detail_resp = await client.get(f"/study-sessions/{session_id}", headers=headers)
    data = detail_resp.json()
    assert data["status"] == "flagged"
    assert data["verified_minutes"] == 0


# ----------------- End Session Tests -----------------

@pytest.mark.asyncio
async def test_end_session_requires_minimum_summary_length(client: AsyncClient):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    response = await client.post(
        f"/study-sessions/{session_id}/end", json={"summary_text": "too short"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_end_session_success_computes_verified_minutes(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # Simulate 5 accumulated minutes of verified study time.
    await _rewind(db_session, session_id, accumulated_seconds=300)

    response = await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Reviewed cell biology chapter 3 and did the practice questions."},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["verified_minutes"] == 5
    assert data["summary_text"].startswith("Reviewed cell biology")

    # Ended session can no longer be interacted with.
    hb_resp = await client.post(f"/study-sessions/{session_id}/heartbeat", headers=headers)
    assert hb_resp.status_code == 400

    # User is now free to start a new session.
    new_start = await client.post("/study-sessions/start", json={}, headers=headers)
    assert new_start.status_code == 201


@pytest.mark.asyncio
async def test_verified_minutes_capped_by_daily_limit(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    # 200 raw minutes exceeds the default 180 min/day cap.
    await _rewind(db_session, session_id, accumulated_seconds=200 * 60)

    response = await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Long cram session before the exam, covered three chapters."},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["verified_minutes"] == 180

    result = await db_session.execute(select(SessionEvent).where(SessionEvent.session_id == session_id))
    events = result.scalars().all()
    assert any(e.event_type == "cap_applied" for e in events)


@pytest.mark.asyncio
async def test_verified_minutes_capped_by_weekly_limit(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    user_result = await db_session.execute(select(User).where(User.username == TEST_USER_DATA["username"]))
    user = user_result.scalar_one()

    # Seed a prior completed session (within the last week) that already used up most of the
    # weekly budget, leaving only 50 minutes of headroom.
    prior = StudySession(
        user_id=user.id,
        status="completed",
        accumulated_seconds=850 * 60,
        verified_minutes=850,
        ended_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(prior)
    await db_session.commit()

    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]
    # 100 raw minutes is under the daily cap (180) but only 50 remain in the weekly budget.
    await _rewind(db_session, session_id, accumulated_seconds=100 * 60)

    response = await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Finished the last few practice sets for chemistry."},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["verified_minutes"] == 50


# ----------------- Ownership / History Tests -----------------

@pytest.mark.asyncio
async def test_user_cannot_access_another_users_session(client: AsyncClient):
    headers = await _auth_headers(client, TEST_USER_DATA)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]

    other_headers = await _auth_headers(client, OTHER_USER_DATA)
    response = await client.get(f"/study-sessions/{session_id}", headers=other_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_sessions_returns_history(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth_headers(client)
    start_resp = await client.post("/study-sessions/start", json={}, headers=headers)
    session_id = start_resp.json()["id"]
    await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Studied algebra for a bit and reviewed old homework."},
        headers=headers
    )

    response = await client.get("/study-sessions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == session_id
