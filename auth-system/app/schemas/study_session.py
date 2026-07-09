from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)


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
