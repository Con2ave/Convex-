from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

QUESTION_COUNT = 10


class QuizStatus(BaseModel):
    """Lightweight quiz summary embedded in StudySessionResponse/Detail so SessionComplete can
    render without a second round trip. Field names mirror the SessionQuiz ORM columns exactly
    (submitted_at, not a derived "submitted" bool) so Pydantic's from_attributes can populate
    this automatically from the session.quiz relationship."""
    status: str  # generating / ready / failed
    passed: Optional[bool] = None
    score: Optional[int] = None
    submitted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionOut(BaseModel):
    """A question as served to the student before grading - no correct_index."""
    question: str
    options: List[str]


class QuizOut(BaseModel):
    status: str
    subject_tag: Optional[str] = None
    questions: Optional[List[QuizQuestionOut]] = None


class QuizSubmitRequest(BaseModel):
    answers: List[int] = Field(..., min_length=QUESTION_COUNT, max_length=QUESTION_COUNT)

    @field_validator("answers")
    @classmethod
    def _answers_in_range(cls, v: List[int]) -> List[int]:
        for a in v:
            if not (0 <= a <= 3):
                raise ValueError("Each answer must be an option index between 0 and 3.")
        return v


class QuizResultOut(BaseModel):
    score: int
    total: int = QUESTION_COUNT
    passed: bool
    correct_answers: List[int]
    is_successful: Optional[bool] = None
