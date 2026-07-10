from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.study_session import StudySession, SessionCheck, SessionEvent, SessionQuiz

# ----------------- Study Session CRUD Operations -----------------

async def create_session(
    db: AsyncSession,
    user_id: int,
    subject_tag: Optional[str],
    next_check_at: datetime,
    target_minutes: Optional[int] = None,
) -> StudySession:
    """Insert a new study session row, already scheduled for its first anti-cheat check.

    target_minutes is only ever passed for guided sessions (see start_guided_session) - every
    existing instant-start call site omits it and behaves exactly as before.
    """
    session = StudySession(
        user_id=user_id,
        subject_tag=subject_tag,
        status="active",
        next_check_at=next_check_at,
        target_minutes=target_minutes,
    )
    db.add(session)
    await db.commit()
    # Re-fetch (rather than db.refresh()) so checks/quiz are eager-loaded up front - a plain
    # refresh() leaves them unloaded, which then triggers a lazy-load during response
    # serialization outside of an awaited context (MissingGreenlet). Same reasoning as
    # save_session below.
    return await get_session_by_id(db, session.id)

async def get_session_by_id(db: AsyncSession, session_id: int) -> Optional[StudySession]:
    """Retrieve a study session by its primary key, with its checks/quiz eager-loaded
    (response schemas may serialize these outside of an active session context)."""
    result = await db.execute(
        select(StudySession)
        .options(selectinload(StudySession.checks), selectinload(StudySession.quiz))
        .where(StudySession.id == session_id)
    )
    return result.scalar_one_or_none()

async def get_open_session_for_user(db: AsyncSession, user_id: int) -> Optional[StudySession]:
    """Return the user's currently active/paused session, if any (only one allowed at a time)."""
    result = await db.execute(
        select(StudySession).where(
            StudySession.user_id == user_id,
            StudySession.status.in_(["active", "paused"])
        )
    )
    return result.scalar_one_or_none()

async def get_user_sessions(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[StudySession]:
    """Retrieve a paginated, most-recent-first study session history for a user.

    Eager-loads quiz - StudySessionResponse (used by both the list and detail routes) now
    serializes it, and a lazy-load during response serialization crashes with MissingGreenlet.
    """
    result = await db.execute(
        select(StudySession)
        .options(selectinload(StudySession.quiz))
        .where(StudySession.user_id == user_id)
        .order_by(StudySession.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def sum_verified_minutes_since(
    db: AsyncSession, user_id: int, since: datetime, exclude_session_id: Optional[int] = None
) -> int:
    """Sum verified_minutes already banked by a user's completed sessions since a given time.
    Used to enforce daily/weekly reward caps before a new session's minutes are finalized."""
    query = select(func.coalesce(func.sum(StudySession.verified_minutes), 0)).where(
        StudySession.user_id == user_id,
        StudySession.status == "completed",
        StudySession.ended_at >= since
    )
    if exclude_session_id is not None:
        query = query.where(StudySession.id != exclude_session_id)
    result = await db.execute(query)
    return result.scalar_one()

async def save_session(db: AsyncSession, session: StudySession) -> StudySession:
    """Persist in-place mutations made to a StudySession instance.

    Re-fetches (rather than db.refresh()) so the eager-loaded `checks` relationship stays
    populated - a plain refresh() expires it, which then triggers a lazy-load during response
    serialization outside of an awaited context (MissingGreenlet).
    """
    db.add(session)
    await db.commit()
    return await get_session_by_id(db, session.id)


# ----------------- Session Check CRUD Operations -----------------

async def create_check(
    db: AsyncSession,
    session_id: int,
    check_type: str,
    prompt: Optional[str],
    expires_at: datetime
) -> SessionCheck:
    """Issue a new anti-cheat check against a session."""
    check = SessionCheck(
        session_id=session_id,
        check_type=check_type,
        prompt=prompt,
        expires_at=expires_at
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return check

async def get_check_by_id(db: AsyncSession, check_id: int) -> Optional[SessionCheck]:
    """Retrieve a session check by its primary key."""
    result = await db.execute(select(SessionCheck).where(SessionCheck.id == check_id))
    return result.scalar_one_or_none()

async def get_pending_check(db: AsyncSession, session_id: int) -> Optional[SessionCheck]:
    """Return the session's unresolved check (passed IS NULL), if any."""
    result = await db.execute(
        select(SessionCheck)
        .where(SessionCheck.session_id == session_id, SessionCheck.passed.is_(None))
        .order_by(SessionCheck.triggered_at.desc())
    )
    return result.scalars().first()

async def save_check(db: AsyncSession, check: SessionCheck) -> SessionCheck:
    """Persist in-place mutations made to a SessionCheck instance."""
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return check

async def count_failed_checks(db: AsyncSession, session_id: int) -> int:
    """Count checks resolved as failed/missed (passed == False) for a session."""
    result = await db.execute(
        select(SessionCheck).where(SessionCheck.session_id == session_id, SessionCheck.passed.is_(False))
    )
    return len(result.scalars().all())


# ----------------- Session Event (Audit Trail) Operations -----------------

async def log_event(db: AsyncSession, session_id: int, event_type: str, detail: Optional[str] = None) -> SessionEvent:
    """Append an immutable audit-trail entry for a session lifecycle transition."""
    event = SessionEvent(session_id=session_id, event_type=event_type, detail=detail)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


# ----------------- Session Quiz CRUD Operations -----------------

async def create_quiz(db: AsyncSession, session_id: int, source_filename: Optional[str]) -> SessionQuiz:
    """Create the quiz row in "generating" state at guided-session-start time; questions are
    filled in later by the background generation task."""
    quiz = SessionQuiz(session_id=session_id, status="generating", source_filename=source_filename)
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz

async def get_quiz_by_session_id(db: AsyncSession, session_id: int) -> Optional[SessionQuiz]:
    result = await db.execute(select(SessionQuiz).where(SessionQuiz.session_id == session_id))
    return result.scalar_one_or_none()

async def save_quiz(db: AsyncSession, quiz: SessionQuiz) -> SessionQuiz:
    """Persist in-place mutations made to a SessionQuiz instance."""
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz
