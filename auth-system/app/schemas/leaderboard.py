from pydantic import BaseModel


class PointsLeaderboardEntry(BaseModel):
    """Deliberately narrow - only username + points ever leaves the server for this endpoint,
    never email/id/role (see app.api.leaderboard, the first cross-user, non-admin endpoint)."""
    username: str
    points: int


class StreakLeaderboardEntry(BaseModel):
    username: str
    streak_days: int
