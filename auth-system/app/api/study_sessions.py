import logging
from typing import List
from fastapi import APIRouter, Depends, status
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
from app.services import study_session as study_session_service

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
