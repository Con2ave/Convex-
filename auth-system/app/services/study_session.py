import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app import crud
from app.models.user import User
from app.models.study_session import StudySession, SessionCheck
from app.schemas.study_session import StudySessionStart, CheckRespondRequest, EndSessionRequest
from app.services import reward as reward_service
from app.services import ai_client
from app.services.text_extraction import extract_text, TextExtractionError

logger = logging.getLogger(__name__)

ATTENTION_PROMPT = "Still there? Tap to confirm you're studying."
RECALL_PROMPT = "In one sentence, what are you studying right now?"
OPEN_STATUSES = ("active", "paused")
MIN_TARGET_MINUTES = 45


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _aware(dt: datetime) -> datetime:
    """Normalize a possibly-naive DB datetime (e.g. SQLite) to UTC-aware for arithmetic."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _next_check_delay() -> timedelta:
    """Randomized 5-10 min interval so attention checks can't be predicted/gamed."""
    seconds = random.randint(settings.STUDY_CHECK_MIN_INTERVAL_SECONDS, settings.STUDY_CHECK_MAX_INTERVAL_SECONDS)
    return timedelta(seconds=seconds)


# ----------------- Session Lifecycle -----------------

async def start_session(db: AsyncSession, user: User, start_in: StudySessionStart) -> StudySession:
    """Start a new study session. Only one active/paused session is allowed per user at a time.

    Free to use - studying and earning Knowledge Points doesn't require a subscription.
    Only cashing KP out for MoMo money does (see app.services.reward.redeem).
    """
    existing = await crud.study_session.get_open_session_for_user(db, user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active study session. End it before starting a new one."
        )

    now = _now()
    session = await crud.study_session.create_session(
        db, user_id=user.id, subject_tag=start_in.subject_tag, next_check_at=now + _next_check_delay()
    )
    await crud.study_session.log_event(db, session.id, "start")
    logger.info(f"Study session {session.id} started for user {user.id}.")
    return session


async def start_guided_session(
    db: AsyncSession,
    user: User,
    background_tasks: BackgroundTasks,
    subject_tag: str,
    target_minutes: int,
    material: UploadFile,
) -> StudySession:
    """Start a session backed by uploaded lecture material: a 10-question quiz is generated in
    the background and served once the session ends (see app.services.quiz). Kept as a separate
    function from start_session rather than merged - the two flows diverge in sequencing (this
    one validates a file and extracts text before anything is created) and instant-start's own
    tests shouldn't have to account for a code path they never exercise.
    """
    if target_minutes < MIN_TARGET_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target study time must be at least {MIN_TARGET_MINUTES} minutes."
        )

    existing = await crud.study_session.get_open_session_for_user(db, user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active study session. End it before starting a new one."
        )

    if not settings.AI_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Guided sessions with AI-generated quizzes aren't available right now."
        )

    try:
        material_text = await extract_text(material)
    except TextExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    now = _now()
    session = await crud.study_session.create_session(
        db,
        user_id=user.id,
        subject_tag=subject_tag,
        next_check_at=now + _next_check_delay(),
        target_minutes=target_minutes,
    )
    quiz = await crud.study_session.create_quiz(db, session.id, source_filename=material.filename)
    # session was fetched (eager-loading quiz) before this row existed, so its in-memory quiz
    # attribute is still stale None - set it directly rather than re-querying again.
    session.quiz = quiz
    await crud.study_session.log_event(db, session.id, "start", detail="guided")

    background_tasks.add_task(_generate_quiz_task, session.id, material_text, subject_tag)

    logger.info(f"Guided study session {session.id} started for user {user.id}; quiz generating.")
    return session


async def _generate_quiz_task(session_id: int, material_text: str, subject_tag: str) -> None:
    """Runs after the start-guided response has already been sent, so it opens its own DB
    session rather than reusing the (by-then-closed) request-scoped one. Never raises past this
    point - a failed background task must not crash the process; it just leaves the quiz
    "failed" for the user to see, and the study session itself is entirely unaffected either way.
    """
    async with async_session_maker() as db:
        quiz = await crud.study_session.get_quiz_by_session_id(db, session_id)
        if not quiz:
            logger.error(f"Quiz row for session {session_id} vanished before generation ran.")
            return
        try:
            questions = await ai_client.generate_quiz(material_text, subject_tag)
            quiz.questions = questions
            quiz.status = "ready"
            logger.info(f"Quiz for session {session_id} generated successfully.")
        except ai_client.AIQuizError as e:
            quiz.status = "failed"
            logger.error(f"Quiz generation failed for session {session_id}: {e}")
        await crud.study_session.save_quiz(db, quiz)


async def get_owned_session(db: AsyncSession, session_id: int, user: User) -> StudySession:
    """Fetch a session the user owns, lazily auto-flagging it if it's gone stale (no heartbeat)."""
    session = await crud.study_session.get_session_by_id(db, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study session not found.")

    if _apply_stale_timeout(session):
        await crud.study_session.log_event(db, session.id, "flag", detail=session.flag_reason)
        session = await crud.study_session.save_session(db, session)

    return session


def _apply_stale_timeout(session: StudySession) -> bool:
    """Flag a session that's gone silent for too long (app killed, network lost, etc). Returns True if changed."""
    if session.status != "active":
        return False

    elapsed_since_activity = (_now() - _aware(session.last_activity_at)).total_seconds()
    if elapsed_since_activity > settings.STUDY_SESSION_STALE_TIMEOUT_SECONDS:
        session.status = "flagged"
        session.flag_reason = "No heartbeat received — session timed out."
        session.ended_at = _aware(session.last_activity_at)
        session.verified_minutes = 0
        return True

    return False


# ----------------- Heartbeat / Timer -----------------

async def heartbeat(db: AsyncSession, session: StudySession) -> Tuple[StudySession, Optional[SessionCheck]]:
    """Client keep-alive ping. Advances server-side verified time by the elapsed gap since the
    last ping (capped at the expected cadence, so a backgrounded/killed app can't be credited),
    resolves any expired anti-cheat check, and surfaces a new one if it's due.
    """
    if session.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is no longer active.")

    now = _now()

    if session.status == "paused":
        session.status = "active"
        await crud.study_session.log_event(db, session.id, "resume", detail="implicit resume via heartbeat")

    elapsed = (now - _aware(session.last_activity_at)).total_seconds()
    if elapsed <= settings.STUDY_HEARTBEAT_GRACE_SECONDS:
        session.accumulated_seconds += int(elapsed)
    else:
        await crud.study_session.log_event(
            db, session.id, "gap", detail=f"{int(elapsed)}s gap between heartbeats — not counted"
        )
    session.last_activity_at = now

    await _resolve_expired_check(db, session)
    await _maybe_flag_for_failures(db, session)

    pending_check = None
    if session.status == "active":
        pending_check = await crud.study_session.get_pending_check(db, session.id)
        if not pending_check and session.next_check_at and _aware(session.next_check_at) <= now:
            pending_check = await _trigger_check(db, session)

    session = await crud.study_session.save_session(db, session)
    return session, pending_check


async def _trigger_check(db: AsyncSession, session: StudySession) -> SessionCheck:
    """Issue a randomized anti-cheat check (mostly attention taps, occasionally a recall question)."""
    now = _now()
    check_type = "recall" if random.random() < 0.3 else "attention"
    if check_type == "recall":
        prompt, window = RECALL_PROMPT, settings.STUDY_RECALL_CHECK_WINDOW_SECONDS
    else:
        prompt, window = ATTENTION_PROMPT, settings.STUDY_ATTENTION_CHECK_WINDOW_SECONDS

    check = await crud.study_session.create_check(
        db, session.id, check_type, prompt, expires_at=now + timedelta(seconds=window)
    )
    session.next_check_at = now + _next_check_delay()
    logger.info(f"Issued {check_type} check {check.id} for session {session.id}.")
    return check


async def _resolve_expired_check(db: AsyncSession, session: StudySession) -> None:
    """Mark the session's pending check as failed if its response window has closed unanswered."""
    pending = await crud.study_session.get_pending_check(db, session.id)
    if pending and _aware(pending.expires_at) < _now():
        pending.passed = False
        await crud.study_session.save_check(db, pending)


async def _maybe_flag_for_failures(db: AsyncSession, session: StudySession) -> None:
    """Auto-flag a session once too many anti-cheat checks have been failed or missed."""
    if session.status != "active":
        return

    failed = await crud.study_session.count_failed_checks(db, session.id)
    if failed >= settings.STUDY_CHECK_MAX_FAILURES:
        session.status = "flagged"
        session.flag_reason = f"Failed or missed {failed} anti-cheat checks."
        session.ended_at = _now()
        await crud.study_session.log_event(db, session.id, "flag", detail=session.flag_reason)
        logger.warning(f"Study session {session.id} auto-flagged: {session.flag_reason}")


# ----------------- Pause / Resume -----------------

async def pause_session(db: AsyncSession, session: StudySession) -> StudySession:
    """Explicit pause (e.g. client detected the app was backgrounded or the screen locked)."""
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an active session can be paused.")

    now = _now()
    elapsed = (now - _aware(session.last_activity_at)).total_seconds()
    if elapsed <= settings.STUDY_HEARTBEAT_GRACE_SECONDS:
        session.accumulated_seconds += int(elapsed)
    session.status = "paused"
    session.last_activity_at = now

    await crud.study_session.log_event(db, session.id, "pause")
    return await crud.study_session.save_session(db, session)


async def resume_session(db: AsyncSession, session: StudySession) -> StudySession:
    """Resume a paused session; the verified-time clock restarts from this moment."""
    if session.status != "paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a paused session can be resumed.")

    session.status = "active"
    session.last_activity_at = _now()

    await crud.study_session.log_event(db, session.id, "resume")
    return await crud.study_session.save_session(db, session)


# ----------------- Anti-cheat Check Responses -----------------

async def respond_to_check(
    db: AsyncSession, session: StudySession, check_id: int, respond_in: CheckRespondRequest
) -> SessionCheck:
    """Answer a pending anti-cheat check (attention tap or recall answer) within its response window."""
    if session.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is no longer active.")

    check = await crud.study_session.get_check_by_id(db, check_id)
    if not check or check.session_id != session.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found.")
    if check.passed is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This check has already been resolved.")

    now = _now()
    check.responded_at = now
    check.response = respond_in.response
    # Grading for v1: a timely, non-empty response passes. Semantic grading of recall answers
    # (e.g. an LLM check that the summary matches the subject) is a phase-3 nice-to-have.
    check.passed = _aware(check.expires_at) >= now and len(respond_in.response.strip()) > 0

    await crud.study_session.save_check(db, check)
    await _maybe_flag_for_failures(db, session)
    await crud.study_session.save_session(db, session)
    return check


async def _apply_reward_caps(db: AsyncSession, session: StudySession, raw_minutes: int) -> int:
    """Clamp raw verified minutes to whatever's left of the user's daily/weekly reward budget.

    Caps payout costs and discourages burnout-style abuse (architecture doc §3.3). Runs on a
    rolling window (last 24h / last 7d) rather than calendar day/week to avoid timezone-boundary
    gaming. This session isn't "completed" in the DB yet at query time, so it can't double-count
    itself - exclude_session_id is just a defensive belt-and-braces guard.
    """
    if raw_minutes <= 0:
        return 0

    now = _now()
    daily_banked = await crud.study_session.sum_verified_minutes_since(
        db, session.user_id, now - timedelta(hours=24), exclude_session_id=session.id
    )
    weekly_banked = await crud.study_session.sum_verified_minutes_since(
        db, session.user_id, now - timedelta(days=7), exclude_session_id=session.id
    )

    daily_remaining = max(0, settings.STUDY_DAILY_VERIFIED_MINUTES_CAP - daily_banked)
    weekly_remaining = max(0, settings.STUDY_WEEKLY_VERIFIED_MINUTES_CAP - weekly_banked)
    capped_minutes = min(raw_minutes, daily_remaining, weekly_remaining)

    if capped_minutes < raw_minutes:
        await crud.study_session.log_event(
            db, session.id, "cap_applied",
            detail=f"Verified minutes capped from {raw_minutes} to {capped_minutes} (daily/weekly reward cap)."
        )
        logger.info(
            f"Study session {session.id} reward-capped: {raw_minutes} -> {capped_minutes} verified minutes."
        )

    return capped_minutes


# ----------------- End of Session -----------------

async def end_session(db: AsyncSession, session: StudySession, end_in: EndSessionRequest) -> StudySession:
    """Close out a session: requires the end-of-session proof summary, finalizes verified minutes."""
    if session.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session has already ended.")

    now = _now()
    if session.status == "active":
        elapsed = (now - _aware(session.last_activity_at)).total_seconds()
        if elapsed <= settings.STUDY_HEARTBEAT_GRACE_SECONDS:
            session.accumulated_seconds += int(elapsed)

    await _resolve_expired_check(db, session)
    await _maybe_flag_for_failures(db, session)

    session.summary_text = end_in.summary_text
    await crud.study_session.log_event(db, session.id, "end")

    if session.status == "flagged":
        session.verified_minutes = 0
    else:
        raw_minutes = session.accumulated_seconds // 60
        session.verified_minutes = await _apply_reward_caps(db, session, raw_minutes)
        session.status = "completed"
    session.ended_at = now

    if session.target_minutes is not None:
        # Raw elapsed time, not the reward-capped verified_minutes - this is about actual time
        # spent, independent of the daily/weekly KP cap. Computed even for a flagged session (an
        # honest label), but the bonus below only ever pays out for a completed one.
        session.target_time_met = (session.accumulated_seconds // 60) >= session.target_minutes

    session = await crud.study_session.save_session(db, session)

    if session.status == "completed":
        # "Perfect" = at least one anti-cheat check was issued and every one passed - a session
        # with zero checks (very short) doesn't count as perfect, it just wasn't tested.
        is_perfect = len(session.checks) > 0 and all(c.passed for c in session.checks)
        await reward_service.award_session_points(
            db, session.user_id, session.id, session.verified_minutes, is_perfect
        )
        if session.target_time_met:
            await reward_service.award_target_time_bonus(db, session.user_id, session.id)

    logger.info(
        f"Study session {session.id} ended for user {session.user_id}: "
        f"status={session.status}, verified_minutes={session.verified_minutes}."
    )
    return session


# ----------------- History -----------------

async def list_sessions(db: AsyncSession, user: User, skip: int = 0, limit: int = 50):
    """Return the user's study session history, most recent first."""
    return await crud.study_session.get_user_sessions(db, user.id, skip, limit)
