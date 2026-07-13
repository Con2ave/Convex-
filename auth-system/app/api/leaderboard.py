import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.leaderboard import PointsLeaderboardEntry, StreakLeaderboardEntry
from app.services import leaderboard as leaderboard_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("/points", response_model=List[PointsLeaderboardEntry])
async def get_points_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Top 50 point-holders by net Knowledge Point balance. Open to any authenticated user -
    returns only username + points, never email/id/role."""
    return await leaderboard_service.get_points_leaderboard(db)


@router.get("/streaks", response_model=List[StreakLeaderboardEntry])
async def get_streak_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Top 50 users by current consecutive-day study streak."""
    return await leaderboard_service.get_streak_leaderboard(db)
