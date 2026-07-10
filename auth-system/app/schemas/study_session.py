from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, computed_field

from app.schemas.quiz import QuizStatus


class StudySessionStart(BaseModel):
    subject_tag: Optional[str] = Field(None, max_length=100, description="Optional subject/topic label for this session")


class SessionCheckResponse(BaseModel):
    id: int
    check_type: str
    prompt: Optional[str] = None
    triggered_at: datetime
    expires_at: datetime
    responded_at: Optional[datetime] = None
    passed: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class StudySessionResponse(BaseModel):
    id: int
    subject_tag: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    accumulated_seconds: int
    verified_minutes: int
    flag_reason: Optional[str] = None

    # Guided-session fields - null for ordinary instant-start sessions.
    target_minutes: Optional[int] = None
    target_time_met: Optional[bool] = None
    quiz: Optional[QuizStatus] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_successful(self) -> Optional[bool]:
        """True only once both halves of a guided session are in: the time target was met AND
        the quiz was passed. None if this isn't a guided session, the session hasn't ended yet,
        or the quiz hasn't been graded yet - not a hard "no"."""
        if self.target_minutes is None or self.target_time_met is None:
            return None
        if self.quiz is None or self.quiz.passed is None:
            return None
        return bool(self.target_time_met and self.quiz.passed)


class StudySessionDetail(StudySessionResponse):
    summary_text: Optional[str] = None
    checks: List[SessionCheckResponse] = []


class HeartbeatResponse(BaseModel):
    status: str
    accumulated_seconds: int
    pending_check: Optional[SessionCheckResponse] = None


class CheckRespondRequest(BaseModel):
    response: str = Field(
        ..., min_length=1, max_length=1000,
        description="Tap acknowledgement (e.g. 'ok') for attention checks, or free-text answer for recall checks"
    )


class EndSessionRequest(BaseModel):
    summary_text: str = Field(
        ..., min_length=20, max_length=2000,
        description="Short summary of what was studied, required to close out the session"
    )
