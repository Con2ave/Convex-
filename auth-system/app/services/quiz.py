"""Post-session comprehension quiz for guided study sessions (see app.services.study_session
.start_guided_session for how the quiz gets generated). Kept separate from study_session.py,
which is already the largest service module in this app.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.study_session import StudySession, SessionQuiz
from app.schemas.quiz import QuizSubmitRequest

logger = logging.getLogger(__name__)

PASSING_SCORE = 7  # out of 10 (70%)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_quiz_for_session(db: AsyncSession, session: StudySession) -> SessionQuiz:
    if session.status in ("active", "paused"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finish the study session before taking its quiz."
        )

    quiz = await crud.study_session.get_quiz_by_session_id(db, session.id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This session has no quiz.")
    return quiz


async def submit_quiz(db: AsyncSession, session: StudySession, submit_in: QuizSubmitRequest) -> SessionQuiz:
    quiz = await get_quiz_for_session(db, session)

    if quiz.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This quiz isn't ready yet." if quiz.status == "generating" else "This quiz couldn't be generated."
        )
    if quiz.submitted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quiz has already been submitted.")

    answers = submit_in.answers
    if len(answers) != len(quiz.questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Expected {len(quiz.questions)} answers, got {len(answers)}."
        )

    score = sum(1 for a, q in zip(answers, quiz.questions) if a == q["correct_index"])

    quiz.answers = answers
    quiz.score = score
    quiz.passed = score >= PASSING_SCORE
    quiz.submitted_at = _now()

    quiz = await crud.study_session.save_quiz(db, quiz)
    logger.info(f"Quiz for session {session.id} submitted: {score}/{len(quiz.questions)}.")
    return quiz
