import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.leaderboard import PointsLeaderboardEntry, StreakLeaderboardEntry
from app.services.reward import STREAK_LOOKBACK_DAYS

logger = logging.getLogger(__name__)

LEADERBOARD_LIMIT = 50


async def get_points_leaderboard(db: AsyncSession, limit: int = LEADERBOARD_LIMIT) -> List[PointsLeaderboardEntry]:
    rows = await crud.reward.get_points_leaderboard(db, limit=limit)
    return [PointsLeaderboardEntry(username=row.username, points=row.points) for row in rows]


async def get_streak_leaderboard(db: AsyncSession, limit: int = LEADERBOARD_LIMIT) -> List[StreakLeaderboardEntry]:
    """All-users counterpart of app.services.reward._streak_and_daily_bonus_eligibility's
    walk-backward algorithm, deliberately kept separate from (and never imported by) that
    function - this reads the same StudySession.ended_at ground truth but purely for ranking,
    so it carries zero regression risk to the tested per-session reward/multiplier flow.

    Pulls every completed-session end-date for every user in the lookback window in one query -
    unlike the points leaderboard, this isn't row-bounded at the SQL layer, since you can't know
    who's in the top N by streak without computing everyone's streak first. Fine at this app's
    current scale; would need revisiting if the user base grew large.
    """
    today = datetime.now(timezone.utc).date()
    since = datetime.combine(today - timedelta(days=STREAK_LOOKBACK_DAYS), time.min, tzinfo=timezone.utc)
    rows = await crud.reward.get_all_completed_session_end_dates(db, since)

    days_by_user: Dict[int, Set[date]] = defaultdict(set)
    username_by_user: Dict[int, str] = {}
    for row in rows:
        if row.ended_at is None:
            continue
        days_by_user[row.user_id].add(row.ended_at.date())
        username_by_user[row.user_id] = row.username

    entries: List[StreakLeaderboardEntry] = []
    for user_id, days in days_by_user.items():
        streak = 0
        cursor = today
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        if streak > 0:
            entries.append(StreakLeaderboardEntry(username=username_by_user[user_id], streak_days=streak))

    entries.sort(key=lambda e: (-e.streak_days, e.username))
    return entries[:limit]
