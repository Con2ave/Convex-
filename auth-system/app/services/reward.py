import asyncio
import logging
import math
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app import crud
from app.models.user import User
from app.models.reward import RewardLedgerEntry, Redemption
from app.schemas.reward import RedeemRequest, RedemptionTier
from app.services import paystack_client
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

SESSION_VERIFIED_REASON = "session_verified"
REDEMPTION_REASON = "redemption:momo"
REDEMPTION_REFUND_REASON = "redemption_refund:momo"

# Guided sessions only (see app.services.study_session.end_session). Purely additive on top of
# the KP formula below - clearing your committed study time is worth a flat bonus regardless of
# how much base KP the session itself earned.
TARGET_TIME_BONUS_KP = 2
TARGET_TIME_BONUS_REASON = "target_time_bonus"

# A "success" transfer status in Paystack test mode comes back immediately, but production
# transfers confirm asynchronously - poll this many times, this far apart, before giving up
# and leaving the redemption "pending" for later reconciliation.
TRANSFER_STATUS_POLL_ATTEMPTS = 3
TRANSFER_STATUS_POLL_DELAY_SECONDS = 2

# ----------------- Earning: Knowledge Points (KP) -----------------
# Deliberately not a transparent per-minute cash rate (students would just do the math) - KP
# is an opaque gamified currency. Most KP comes from actually studying; trivial actions are
# worth very little. See app.models.reward.RewardLedgerEntry docstring.

STUDY_BLOCK_MINUTES = 30
KP_PER_STUDY_BLOCK = 10          # a clean 2h session = 40 KP before bonuses
PERFECT_SESSION_BONUS_KP = 10    # zero missed/failed anti-cheat checks (must have answered at least one)
DAILY_FIRST_SESSION_BONUS_KP = 2  # small nudge for showing up - no app-open tracking, so this
                                   # is "your first *completed* session today" as the closest proxy

# Streak multiplier, capped at 2.5x so a long streak can't run the payout budget away.
# (threshold_days, multiplier), checked highest-first.
STREAK_MULTIPLIERS: List[tuple] = [
    (60, Decimal("2.5")),
    (30, Decimal("2.0")),
    (14, Decimal("1.5")),
    (7, Decimal("1.2")),
    (1, Decimal("1.0")),
]

STREAK_LOOKBACK_DAYS = 70  # comfortably covers the 60-day multiplier tier


def _streak_multiplier(streak_days: int) -> Decimal:
    for threshold, multiplier in STREAK_MULTIPLIERS:
        if streak_days >= threshold:
            return multiplier
    return Decimal("1.0")


async def _streak_and_daily_bonus_eligibility(
    db: AsyncSession, user_id: int, session_id: int, today: date
) -> tuple:
    """Returns (streak_days_including_today, is_first_completed_session_today)."""
    since = datetime.combine(today - timedelta(days=STREAK_LOOKBACK_DAYS), time.min, tzinfo=timezone.utc)
    ended_ats = await crud.reward.get_completed_session_end_dates(
        db, user_id, since, exclude_session_id=session_id
    )
    days_with_session = {dt.date() for dt in ended_ats}
    is_first_today = today not in days_with_session

    days_with_session.add(today)  # the session being completed right now counts toward today's streak
    streak = 0
    cursor = today
    while cursor in days_with_session:
        streak += 1
        cursor -= timedelta(days=1)

    return streak, is_first_today


async def award_session_points(
    db: AsyncSession, user_id: int, session_id: int, verified_minutes: int, is_perfect: bool
) -> int:
    """Credit a user's ledger for a completed, verified study session.

    KP = (study-time blocks + perfect bonus + daily-first-session bonus) x streak multiplier,
    floored - the app never rounds a fraction of a point in the student's favor.

    Idempotent per session: if end_session were ever somehow invoked twice for the same
    session, this won't double-award (guards against the ledger drifting from reality).
    """
    if await crud.reward.has_ledger_entry_for_session(db, session_id, SESSION_VERIFIED_REASON):
        logger.warning(f"Skipped duplicate point award for session {session_id} (already credited).")
        return 0

    today = datetime.now(timezone.utc).date()
    streak_days, is_first_today = await _streak_and_daily_bonus_eligibility(db, user_id, session_id, today)

    base_kp = (verified_minutes // STUDY_BLOCK_MINUTES) * KP_PER_STUDY_BLOCK
    bonus_kp = 0
    if is_perfect and verified_minutes > 0:
        bonus_kp += PERFECT_SESSION_BONUS_KP
    if is_first_today:
        bonus_kp += DAILY_FIRST_SESSION_BONUS_KP

    multiplier = _streak_multiplier(streak_days)
    kp = math.floor((base_kp + bonus_kp) * multiplier)

    if kp <= 0:
        return 0

    await crud.reward.create_ledger_entry(
        db, user_id=user_id, points=kp, reason=SESSION_VERIFIED_REASON, session_id=session_id
    )
    logger.info(
        f"Awarded {kp} KP to user {user_id} for session {session_id} "
        f"(base={base_kp}, bonus={bonus_kp}, streak={streak_days}d x{multiplier})."
    )
    return kp


async def award_target_time_bonus(db: AsyncSession, user_id: int, session_id: int) -> int:
    """Flat +2 KP for clearing a guided session's target study time. Idempotent per session,
    same guard pattern as award_session_points."""
    if await crud.reward.has_ledger_entry_for_session(db, session_id, TARGET_TIME_BONUS_REASON):
        logger.warning(f"Skipped duplicate target-time bonus for session {session_id} (already credited).")
        return 0

    await crud.reward.create_ledger_entry(
        db, user_id=user_id, points=TARGET_TIME_BONUS_KP, reason=TARGET_TIME_BONUS_REASON, session_id=session_id
    )
    logger.info(f"Awarded {TARGET_TIME_BONUS_KP} KP target-time bonus to user {user_id} for session {session_id}.")
    return TARGET_TIME_BONUS_KP


async def get_balance(db: AsyncSession, user: User) -> int:
    return await crud.reward.get_balance(db, user.id)


async def list_ledger(db: AsyncSession, user: User, skip: int = 0, limit: int = 50) -> List[RewardLedgerEntry]:
    return await crud.reward.get_ledger(db, user.id, skip, limit)


async def list_redemptions(db: AsyncSession, user: User, skip: int = 0, limit: int = 50) -> List[Redemption]:
    return await crud.reward.get_redemptions(db, user.id, skip, limit)


# ----------------- Redemption: fixed MoMo cash tiers -----------------
# Larger denominations cost disproportionately more KP per GHS, not just linearly more -
# makes big redemptions feel meaningfully further away, not just "further along the same line".
REDEMPTION_TIERS: List[RedemptionTier] = [
    RedemptionTier(ghs_amount=1, kp_cost=300),
    RedemptionTier(ghs_amount=2, kp_cost=600),
    RedemptionTier(ghs_amount=5, kp_cost=1500),
    RedemptionTier(ghs_amount=10, kp_cost=3500),
]


def get_redemption_tiers() -> List[RedemptionTier]:
    return REDEMPTION_TIERS


def _find_tier(ghs_amount: int) -> Optional[RedemptionTier]:
    return next((t for t in REDEMPTION_TIERS if t.ghs_amount == ghs_amount), None)


async def _payout_mock(tier: RedemptionTier, recipient_phone: str) -> tuple:
    """Dev/demo fallback when no real Paystack credentials are configured - logged rather than
    actually dispatched, mirroring the mock-email-service pattern already used for auth flows."""
    mock_ref = f"MOCK-MOMO-{uuid.uuid4().hex[:10].upper()}"
    logger.warning(
        f"[MOCK MOMO SERVICE] Would send GHS {tier.ghs_amount} MoMo cash to {recipient_phone} "
        f"for {tier.kp_cost} KP. Provider ref: {mock_ref}"
    )
    return "completed", mock_ref


async def _payout_paystack(
    redemption_id: int, tier: RedemptionTier, recipient_name: str, recipient_phone: str, network: str
) -> tuple:
    """Real Paystack Transfer payout. Test-mode transfers usually report "success" immediately;
    production ones confirm asynchronously - poll a few times for the real outcome, and if
    it's still unresolved after that, leave it "pending" for later reconciliation (no
    background worker exists yet to do this automatically)."""
    try:
        recipient_code = await paystack_client.create_transfer_recipient(recipient_name, recipient_phone, network)
        transfer = await paystack_client.initiate_transfer(
            recipient_code=recipient_code,
            amount_ghs=tier.ghs_amount,
            reason=f"GHS {tier.ghs_amount} study reward",
            reference=f"redemption-{redemption_id}"
        )
    except paystack_client.PaystackError as e:
        logger.error(f"Paystack transfer request failed for redemption {redemption_id}: {e}")
        return "failed", None

    transfer_code = transfer["transfer_code"]
    if transfer["status"] == "success":
        return "completed", transfer_code
    if transfer["status"] == "failed":
        return "failed", transfer_code

    for _ in range(TRANSFER_STATUS_POLL_ATTEMPTS):
        await asyncio.sleep(TRANSFER_STATUS_POLL_DELAY_SECONDS)
        try:
            transfer_status = await paystack_client.get_transfer_status(transfer_code)
        except paystack_client.PaystackError as e:
            logger.error(f"Paystack status check failed for redemption {redemption_id}: {e}")
            break
        if transfer_status == "success":
            return "completed", transfer_code
        if transfer_status in ("failed", "reversed"):
            return "failed", transfer_code

    logger.warning(f"Paystack transfer for redemption {redemption_id} still pending after polling - will need reconciliation.")
    return "pending", transfer_code


async def redeem(db: AsyncSession, user: User, redeem_in: RedeemRequest) -> Redemption:
    """Redeem KP for MoMo cash at a fixed tier (phase 1 per the architecture doc - no
    raffles/chance-based payouts, merit-based only).

    Studying and earning KP is free for everyone; cashing KP out requires an active
    subscription (admins exempt). Declining to subscribe never blocks app usage, only payout -
    the KP just sits in the balance until the user subscribes, whenever that is.
    """
    if user.role != "admin" and not await subscription_service.has_active_subscription(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription is required to redeem Knowledge Points for cash. "
                   "Subscribe from your profile to unlock cash redemptions."
        )

    tier = _find_tier(redeem_in.ghs_amount)
    if tier is None:
        available = ", ".join(f"GHS {t.ghs_amount}" for t in REDEMPTION_TIERS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GHS {redeem_in.ghs_amount} isn't an available redemption tier. Choose from: {available}."
        )

    balance = await crud.reward.get_balance(db, user.id)
    if tier.kp_cost > balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. You have {balance} KP; this tier costs {tier.kp_cost} KP."
        )

    redemption = await crud.reward.create_redemption(
        db,
        user_id=user.id,
        points_spent=tier.kp_cost,
        ghs_amount=tier.ghs_amount,
        recipient_phone=redeem_in.recipient_phone,
        network=redeem_in.network,
        status="pending",
        provider_ref=None,
        reward_type="momo"
    )
    await crud.reward.create_ledger_entry(
        db, user_id=user.id, points=-tier.kp_cost, reason=REDEMPTION_REASON
    )

    if settings.PAYSTACK_CONFIGURED:
        final_status, provider_ref = await _payout_paystack(
            redemption.id, tier, user.username, redeem_in.recipient_phone, redeem_in.network
        )
    else:
        final_status, provider_ref = await _payout_mock(tier, redeem_in.recipient_phone)

    if final_status == "failed":
        # Give the KP back - the redemption never actually happened.
        await crud.reward.create_ledger_entry(
            db, user_id=user.id, points=tier.kp_cost, reason=REDEMPTION_REFUND_REASON
        )
        logger.warning(f"Refunded {tier.kp_cost} KP to user {user.id} after failed redemption {redemption.id}.")

    redemption.status = final_status
    redemption.provider_ref = provider_ref
    redemption = await crud.reward.save_redemption(db, redemption)

    logger.info(
        f"User {user.id} redemption {redemption.id}: {tier.kp_cost} KP -> GHS {tier.ghs_amount} MoMo "
        f"({redemption.recipient_phone}), status={final_status}."
    )
    return redemption
