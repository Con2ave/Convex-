from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from app.core.database import Base


class RewardLedgerEntry(Base):
    """Immutable append-only ledger. A user's point balance is always SUM(points) over
    their entries - never stored/mutated directly - so it can never drift from its history.

    Points are "Knowledge Points" (KP), a gamified currency deliberately decoupled from GHS -
    the conversion only shows up at redemption time via fixed, non-linear MoMo cash tiers
    (see app.services.reward.REDEMPTION_TIERS), not a transparent per-point cash rate.
    """
    __tablename__ = "reward_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="SET NULL"), nullable=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # KP; positive = earned, negative = redeemed
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. session_verified, redemption:momo
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Redemption(Base):
    __tablename__ = "redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)  # KP cost of the tier
    ghs_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # MoMo cash value actually delivered
    reward_type: Mapped[str] = mapped_column(String(20), nullable=False, default="momo")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/completed/failed
    provider_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    network: Mapped[str] = mapped_column(String(20), nullable=False)  # mtn / telecel / airteltigo
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
