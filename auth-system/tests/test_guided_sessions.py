import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.study_session import StudySession
from app.models.reward import RewardLedgerEntry
from app.models.user import User
from app.services import ai_client

TEST_USER_DATA = {
    "username": "guideduser",
    "email": "guideduser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

# 10 valid questions the mocked AI client returns by default.
VALID_QUESTIONS = [
    {"question": f"Question {i}?", "options": ["A", "B", "C", "D"], "correct_index": 0}
    for i in range(10)
]


async def _auth_headers(client: AsyncClient, user_data: dict = TEST_USER_DATA) -> dict:
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


def _mock_ai_success(monkeypatch, questions=None):
    # start_guided_session gates on settings.AI_CONFIGURED before ever reaching generate_quiz,
    # so a mocked function alone isn't enough - a real deployment would have a real key here.
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    async def fake_generate_quiz(material_text: str, subject: str):
        return questions if questions is not None else [dict(q) for q in VALID_QUESTIONS]
    monkeypatch.setattr(ai_client, "generate_quiz", fake_generate_quiz)


def _mock_ai_failure(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    async def fake_generate_quiz(material_text: str, subject: str):
        raise ai_client.AIQuizError("simulated failure")
    monkeypatch.setattr(ai_client, "generate_quiz", fake_generate_quiz)


async def _start_guided(
    client: AsyncClient, headers: dict, db_session: AsyncSession, target_minutes: int = 45,
    filename="notes.txt", content=b"x" * 500,
):
    response = await client.post(
        "/study-sessions/start-guided",
        data={"subject_tag": "Biology", "target_minutes": str(target_minutes)},
        files={"material": (filename, content, "text/plain")},
        headers=headers,
    )
    # The quiz background task runs under its own, separate DB session (see
    # study_session._generate_quiz_task) - it commits fine, but the test's shared db_session
    # fixture (expire_on_commit=False) may already hold a stale, pre-generation copy of the
    # SessionQuiz row in its identity map from the request that just ran. Expire it so later
    # reads on db_session (and, through the same override, the client's own subsequent requests)
    # go back to the database instead of returning cached stale attributes.
    db_session.expire_all()
    return response


async def _end_session(client: AsyncClient, headers: dict, session_id: int):
    return await client.post(
        f"/study-sessions/{session_id}/end",
        json={"summary_text": "Studied the uploaded lecture notes end to end today."},
        headers=headers,
    )


# ----------------- Start guided session -----------------

@pytest.mark.asyncio
async def test_start_guided_session_success(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    response = await _start_guided(client, headers, db_session)
    assert response.status_code == 201
    data = response.json()
    assert data["target_minutes"] == 45
    assert data["target_time_met"] is None
    # The response body is serialized before background tasks run (even under the ASGI test
    # transport, where the whole request - including the background task - completes before
    # this call returns), so the quiz is still "generating" in this exact response.
    assert data["quiz"]["status"] == "generating"

    quiz_resp = await client.get(f"/study-sessions/{data['id']}", headers=headers)
    assert quiz_resp.json()["quiz"]["status"] == "ready"


@pytest.mark.asyncio
async def test_start_guided_session_below_floor_rejected(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    response = await _start_guided(client, headers, db_session, target_minutes=30)
    assert response.status_code == 400

    result = await client.get("/study-sessions", headers=headers)
    assert result.json() == []


@pytest.mark.asyncio
async def test_start_guided_session_bad_file_type_rejected(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    response = await _start_guided(client, headers, db_session, filename="notes.png", content=b"not text")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_start_guided_session_oversized_file_rejected(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    oversized = b"x" * (10 * 1024 * 1024 + 1)
    response = await _start_guided(client, headers, db_session, content=oversized)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_start_guided_session_blocked_by_open_session(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    first = await _start_guided(client, headers, db_session)
    assert first.status_code == 201

    second = await _start_guided(client, headers, db_session)
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_start_guided_session_ai_generation_failure(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_failure(monkeypatch)
    headers = await _auth_headers(client)

    response = await _start_guided(client, headers, db_session)
    assert response.status_code == 201  # the session itself starts fine regardless

    session_id = response.json()["id"]
    quiz_resp = await client.get(f"/study-sessions/{session_id}/quiz", headers=headers)
    # session hasn't ended yet, so the quiz isn't fetchable regardless of its generation status
    assert quiz_resp.status_code == 400


@pytest.mark.asyncio
async def test_instant_start_unaffected_by_guided_session_fields(client: AsyncClient):
    """Regression: the existing instant-start endpoint's response shape still includes the new
    nullable fields as null, and nothing about it changed."""
    headers = await _auth_headers(client)
    response = await client.post("/study-sessions/start", json={"subject_tag": "Physics"}, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["target_minutes"] is None
    assert data["target_time_met"] is None
    assert data["quiz"] is None
    assert data["is_successful"] is None


# ----------------- Quiz access + submission -----------------

@pytest.mark.asyncio
async def test_quiz_not_accessible_before_session_ends(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session)
    session_id = start_resp.json()["id"]

    response = await client.get(f"/study-sessions/{session_id}/quiz", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_quiz_score_exactly_seventy_percent_passes(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session)
    session_id = start_resp.json()["id"]
    await _end_session(client, headers, session_id)

    quiz_resp = await client.get(f"/study-sessions/{session_id}/quiz", headers=headers)
    assert quiz_resp.json()["status"] == "ready"

    # correct_index is always 0 in VALID_QUESTIONS; answer 7 correctly, 3 incorrectly.
    answers = [0] * 7 + [1] * 3
    submit_resp = await client.post(
        f"/study-sessions/{session_id}/quiz/submit", json={"answers": answers}, headers=headers
    )
    assert submit_resp.status_code == 200
    result = submit_resp.json()
    assert result["score"] == 7
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_quiz_score_just_below_seventy_percent_fails(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session)
    session_id = start_resp.json()["id"]
    await _end_session(client, headers, session_id)

    answers = [0] * 6 + [1] * 4
    submit_resp = await client.post(
        f"/study-sessions/{session_id}/quiz/submit", json={"answers": answers}, headers=headers
    )
    assert submit_resp.status_code == 200
    result = submit_resp.json()
    assert result["score"] == 6
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_quiz_cannot_be_submitted_twice(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session)
    session_id = start_resp.json()["id"]
    await _end_session(client, headers, session_id)

    answers = [0] * 10
    first = await client.post(f"/study-sessions/{session_id}/quiz/submit", json={"answers": answers}, headers=headers)
    assert first.status_code == 200

    second = await client.post(f"/study-sessions/{session_id}/quiz/submit", json={"answers": answers}, headers=headers)
    assert second.status_code == 400


# ----------------- Target-time bonus + is_successful -----------------

@pytest.mark.asyncio
async def test_target_time_bonus_awarded_when_met(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
    session_id = start_resp.json()["id"]

    await db_session.execute(
        update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=50 * 60)
    )
    await db_session.commit()

    end_resp = await _end_session(client, headers, session_id)
    assert end_resp.json()["target_time_met"] is True

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    reasons = [e["reason"] for e in ledger_resp.json()]
    assert reasons.count("target_time_bonus") == 1
    bonus_entry = next(e for e in ledger_resp.json() if e["reason"] == "target_time_bonus")
    assert bonus_entry["points"] == 2


@pytest.mark.asyncio
async def test_target_time_bonus_withheld_when_not_met(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
    session_id = start_resp.json()["id"]
    # No backdating - accumulated_seconds stays near 0, well under the 45 min target.

    end_resp = await _end_session(client, headers, session_id)
    assert end_resp.json()["target_time_met"] is False

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    reasons = [e["reason"] for e in ledger_resp.json()]
    assert "target_time_bonus" not in reasons


@pytest.mark.asyncio
async def test_target_time_bonus_idempotent(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from app.services import reward as reward_service

    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
    session_id = start_resp.json()["id"]
    user_id = await _get_user_id(db_session, TEST_USER_DATA["username"])

    await db_session.execute(
        update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=50 * 60)
    )
    await db_session.commit()
    await _end_session(client, headers, session_id)

    # Calling it again directly (simulating a retried end_session) must not double-credit.
    await reward_service.award_target_time_bonus(db_session, user_id, session_id)

    ledger_resp = await client.get("/rewards/ledger", headers=headers)
    reasons = [e["reason"] for e in ledger_resp.json()]
    assert reasons.count("target_time_bonus") == 1


@pytest.mark.asyncio
async def test_is_successful_truth_table(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)

    # met + passed -> True
    start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
    session_id = start_resp.json()["id"]
    await db_session.execute(
        update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=50 * 60)
    )
    await db_session.commit()

    # Before the quiz is submitted, is_successful must be null (not yet graded), not False.
    mid_resp = await client.get(f"/study-sessions/{session_id}", headers=headers)
    assert mid_resp.json()["is_successful"] is None

    await _end_session(client, headers, session_id)
    await client.post(
        f"/study-sessions/{session_id}/quiz/submit", json={"answers": [0] * 10}, headers=headers
    )
    final_resp = await client.get(f"/study-sessions/{session_id}", headers=headers)
    assert final_resp.json()["is_successful"] is True


@pytest.mark.asyncio
async def test_is_successful_false_when_met_but_quiz_failed(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    _mock_ai_success(monkeypatch)
    headers = await _auth_headers(client)
    start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
    session_id = start_resp.json()["id"]
    await db_session.execute(
        update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=50 * 60)
    )
    await db_session.commit()
    await _end_session(client, headers, session_id)

    await client.post(
        f"/study-sessions/{session_id}/quiz/submit", json={"answers": [1] * 10}, headers=headers
    )
    final_resp = await client.get(f"/study-sessions/{session_id}", headers=headers)
    assert final_resp.json()["is_successful"] is False


@pytest.mark.asyncio
async def test_quiz_outcome_never_affects_base_kp(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Base session_verified KP must be identical whether the quiz is passed or failed - the
    quiz only ever affects the separate is_successful label, never the reward formula."""
    _mock_ai_success(monkeypatch)

    async def _run(username_suffix: str, answers: list) -> int:
        user_data = {**TEST_USER_DATA, "username": f"quizkp{username_suffix}", "email": f"quizkp{username_suffix}@example.com"}
        headers = await _auth_headers(client, user_data)
        start_resp = await _start_guided(client, headers, db_session, target_minutes=45)
        session_id = start_resp.json()["id"]
        await db_session.execute(
            update(StudySession).where(StudySession.id == session_id).values(accumulated_seconds=90 * 60)
        )
        await db_session.commit()
        await _end_session(client, headers, session_id)
        await client.post(f"/study-sessions/{session_id}/quiz/submit", json={"answers": answers}, headers=headers)

        ledger_resp = await client.get("/rewards/ledger", headers=headers)
        entry = next(e for e in ledger_resp.json() if e["reason"] == "session_verified")
        return entry["points"]

    kp_passed = await _run("a", [0] * 10)
    kp_failed = await _run("b", [1] * 10)
    assert kp_passed == kp_failed
