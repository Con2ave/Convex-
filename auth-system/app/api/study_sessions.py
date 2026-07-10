import logging
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.study_session import (
    StudySessionStart,
    StudySessionResponse,
    StudySessionDetail,
    HeartbeatResponse,
    CheckRespondRequest,
    SessionCheckResponse,
    EndSessionRequest,
)
from app.schemas.quiz import QuizOut, QuizQuestionOut, QuizSubmitRequest, QuizResultOut
from app.services import study_session as study_session_service
from app.services import quiz as quiz_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-sessions", tags=["Study Sessions"])


@router.post("/start", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    start_in: StudySessionStart,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Start a new study session. Rejects the request if the user already has one open."""
    return await study_session_service.start_session(db, current_user, start_in)


@router.post("/start-guided", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
async def start_guided_session(
    background_tasks: BackgroundTasks,
    subject_tag: str = Form(..., max_length=100),
    target_minutes: int = Form(...),
    material: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Start a session backed by uploaded lecture material (PDF or .txt).

    A 10-question comprehension quiz is generated in the background from the material and is
    ready by the time the session ends - see GET /{session_id}/quiz.
    """
    return await study_session_service.start_guided_session(
        db, current_user, background_tasks, subject_tag, target_minutes, material
    )


@router.get("", response_model=List[StudySessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List the current user's study session history, most recent first."""
    return await study_session_service.list_sessions(db, current_user, skip, limit)


@router.get("/{session_id}", response_model=StudySessionDetail)
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve full detail for one session, including its anti-cheat check history."""
    return await study_session_service.get_owned_session(db, session_id, current_user)


@router.post("/{session_id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Client keep-alive ping, expected roughly every 20-30s while the app is foregrounded.

    Advances server-side verified time, resolves any expired anti-cheat check, and returns
    a new check when one is due for the client to prompt the user with.
    """
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    session, pending_check = await study_session_service.heartbeat(db, session)
    return HeartbeatResponse(
        status=session.status,
        accumulated_seconds=session.accumulated_seconds,
        pending_check=pending_check
    )


@router.post("/{session_id}/pause", response_model=StudySessionResponse)
async def pause_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Explicitly pause a session (e.g. client detected the app was backgrounded or screen locked)."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    return await study_session_service.pause_session(db, session)


@router.post("/{session_id}/resume", response_model=StudySessionResponse)
async def resume_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Resume a previously paused session."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    return await study_session_service.resume_session(db, session)


@router.post("/{session_id}/checks/{check_id}/respond", response_model=SessionCheckResponse)
async def respond_to_check(
    session_id: int,
    check_id: int,
    respond_in: CheckRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Respond to a pending anti-cheat check (attention tap or recall answer) within its window."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    return await study_session_service.respond_to_check(db, session, check_id, respond_in)


@router.post("/{session_id}/end", response_model=StudySessionDetail)
async def end_session(
    session_id: int,
    end_in: EndSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """End a session by submitting the required end-of-session summary, finalizing verified minutes."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    return await study_session_service.end_session(db, session, end_in)


@router.get("/{session_id}/quiz", response_model=QuizOut)
async def get_quiz(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Fetch this session's quiz. Questions are omitted until generation finishes (status
    "ready"), and correct answers are never included here - only after grading."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    quiz = await quiz_service.get_quiz_for_session(db, session)
    return QuizOut(
        status=quiz.status,
        subject_tag=session.subject_tag,
        questions=(
            [QuizQuestionOut(question=q["question"], options=q["options"]) for q in quiz.questions]
            if quiz.status == "ready" else None
        ),
    )


@router.post("/{session_id}/quiz/submit", response_model=QuizResultOut)
async def submit_quiz(
    session_id: int,
    submit_in: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Grade the quiz. One-time - a second submit attempt is rejected."""
    session = await study_session_service.get_owned_session(db, session_id, current_user)
    quiz = await quiz_service.submit_quiz(db, session, submit_in)

    is_successful = (
        bool(session.target_time_met and quiz.passed)
        if session.target_time_met is not None else None
    )
    return QuizResultOut(
        score=quiz.score,
        passed=quiz.passed,
        correct_answers=[q["correct_index"] for q in quiz.questions],
        is_successful=is_successful,
    )
