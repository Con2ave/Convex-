from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.reward import RewardLedgerEntry, Redemption
from app.models.study_session import StudySession

# ----------------- Ledger -----------------

async def create_ledger_entry(
    db: AsyncSession, user_id: int, points: int, reason: str, session_id: Optional[int] = None
) -> RewardLedgerEntry:
    """Append an immutable ledger entry. Positive points = earned, negative = spent/adjusted."""
    entry = RewardLedgerEntry(user_id=user_id, points=points, reason=reason, session_id=session_id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry

async def get_balance(db: AsyncSession, user_id: int) -> int:
    """A user's point balance is always derived by summing their ledger - never stored directly."""
    result = await db.execute(
        select(func.coalesce(func.sum(RewardLedgerEntry.points), 0)).where(RewardLedgerEntry.user_id == user_id)
    )
    return result.scalar_one()

async def get_ledger(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[RewardLedgerEntry]:
    """Retrieve a paginated, most-recent-first transaction history for a user.

    Ties on created_at (SQLite's CURRENT_TIMESTAMP is only second-resolution, so two
    entries in the same second are common - e.g. a session award immediately redeemed)
    are broken by id so ordering always matches insertion order.
    """
    result = await db.execute(
        select(RewardLedgerEntry)
        .where(RewardLedgerEntry.user_id == user_id)
        .order_by(RewardLedgerEntry.created_at.desc(), RewardLedgerEntry.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def has_ledger_entry_for_session(db: AsyncSession, session_id: int, reason: str) -> bool:
    """Guards against double-awarding points if end_session were ever called twice for one session."""
    result = await db.execute(
        select(RewardLedgerEntry.id).where(
            RewardLedgerEntry.session_id == session_id, RewardLedgerEntry.reason == reason
        )
    )
    return result.scalar_one_or_none() is not None


# ----------------- Streak / Daily-bonus support -----------------

async def get_completed_session_end_dates(
    db: AsyncSession, user_id: int, since: datetime, exclude_session_id: Optional[int] = None
) -> List[datetime]:
    """Raw ended_at timestamps for a user's completed sessions since a given time.
    Used to compute the study streak and whether today's first session bonus has fired -
    both are simplest to work out in Python once the raw dates are in hand."""
    query = select(StudySession.ended_at).where(
        StudySession.user_id == user_id,
        StudySession.status == "completed",
        StudySession.ended_at >= since
    )
    if exclude_session_id is not None:
        query = query.where(StudySession.id != exclude_session_id)
    result = await db.execute(query)
    return [row[0] for row in result.all() if row[0] is not None]


# ----------------- Redemptions -----------------

async def create_redemption(
    db: AsyncSession,
    user_id: int,
    points_spent: int,
    ghs_amount: int,
    recipient_phone: str,
    network: str,
    status: str,
    provider_ref: Optional[str],
    reward_type: str = "momo"
) -> Redemption:
    redemption = Redemption(
        user_id=user_id,
        points_spent=points_spent,
        ghs_amount=ghs_amount,
        reward_type=reward_type,
        status=status,
        provider_ref=provider_ref,
        recipient_phone=recipient_phone,
        network=network
    )
    db.add(redemption)
    await db.commit()
    await db.refresh(redemption)
    return redemption

async def get_redemptions(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[Redemption]:
    result = await db.execute(
        select(Redemption)
        .where(Redemption.user_id == user_id)
        .order_by(Redemption.created_at.desc(), Redemption.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def save_redemption(db: AsyncSession, redemption: Redemption) -> Redemption:
    """Persist in-place mutations made to a Redemption instance (e.g. status transitions)."""
    db.add(redemption)
    await db.commit()
    await db.refresh(redemption)
    return redemption
