"""Generates a 10-question comprehension quiz from a student's uploaded lecture material.

Currently backed by Google Gemini's free tier so this feature can be built and tested without
spending money. generate_quiz() is the entire public surface - everything else in this file is
an implementation detail, so swapping to Claude later (once this ships to real users) means
rewriting the inside of this file only, not any of its callers.
"""
import logging
from typing import List

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_MS = 45_000
_MAX_MATERIAL_CHARS = 15_000
_QUESTION_COUNT = 10
_OPTION_COUNT = 4


class AIQuizError(Exception):
    """Raised whenever a usable 10-question quiz couldn't be produced."""


class _QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_index: int


class _QuizResponse(BaseModel):
    questions: List[_QuizQuestion]


def _build_prompt(material_text: str, subject: str, correction: str | None = None) -> str:
    base = (
        f"You are writing a comprehension quiz for a student studying \"{subject}\".\n"
        f"Based only on the lecture material below, write exactly {_QUESTION_COUNT} multiple-choice "
        f"questions. Each question must have exactly {_OPTION_COUNT} answer options with exactly one "
        "correct answer. Questions should test understanding of the material, not trivia about its "
        "formatting. correct_index is 0-based (0-3).\n\n"
        f"Lecture material:\n{material_text[:_MAX_MATERIAL_CHARS]}"
    )
    if correction:
        base += f"\n\nYour previous attempt was invalid: {correction}. Try again, exactly {_QUESTION_COUNT} questions."
    return base


def _validate(questions: List[_QuizQuestion]) -> str | None:
    """Returns a description of what's wrong, or None if the quiz is usable."""
    if len(questions) != _QUESTION_COUNT:
        return f"returned {len(questions)} questions instead of {_QUESTION_COUNT}"
    for i, q in enumerate(questions):
        if len(q.options) != _OPTION_COUNT:
            return f"question {i + 1} has {len(q.options)} options instead of {_OPTION_COUNT}"
        if not (0 <= q.correct_index < _OPTION_COUNT):
            return f"question {i + 1} has correct_index {q.correct_index} out of range"
    return None


async def generate_quiz(material_text: str, subject: str) -> list[dict]:
    """Returns exactly 10 {"question", "options" (4 strings), "correct_index"} dicts.

    Retries once with a corrective prompt if the model returns the wrong question/option count
    or an out-of-range correct_index - a JSON schema alone can't enforce array length, so this is
    validated here rather than trusted from the response.
    """
    if not settings.AI_CONFIGURED:
        raise AIQuizError("AI quiz generation is not configured.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    correction: str | None = None

    for attempt in range(2):
        prompt = _build_prompt(material_text, subject, correction)
        try:
            response = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_QuizResponse,
                ),
            )
        except Exception as e:
            logger.error(f"Quiz generation request failed (attempt {attempt + 1}): {e}")
            raise AIQuizError("The quiz generation request failed.") from e

        parsed = response.parsed
        if parsed is None:
            correction = "the response wasn't valid JSON"
            logger.warning(f"Quiz generation returned unparseable output (attempt {attempt + 1}).")
            continue

        correction = _validate(parsed.questions)
        if correction is None:
            return [q.model_dump() for q in parsed.questions]
        logger.warning(f"Quiz generation attempt {attempt + 1} invalid: {correction}")

    raise AIQuizError("Couldn't generate a valid quiz from this material after retrying.")
