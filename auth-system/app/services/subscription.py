import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app import crud
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.subscription import (
    SubscriptionPlan,
    InitializeSubscriptionRequest,
    InitializeSubscriptionResponse,
    SubscriptionStatus,
)
from app.services import paystack_client

logger = logging.getLogger(__name__)

# GHS 20/3mo and GHS 80/year are both discounts vs. paying monthly (30 and 120 respectively) -
# the usual "commit longer, pay less per month" subscription pricing shape.
SUBSCRIPTION_PLANS: List[SubscriptionPlan] = [
    SubscriptionPlan(plan="monthly", ghs_amount=10, duration_days=30),
    SubscriptionPlan(plan="quarterly", ghs_amount=20, duration_days=90),
    SubscriptionPlan(plan="annual", ghs_amount=80, duration_days=365),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def list_plans() -> List[SubscriptionPlan]:
    return SUBSCRIPTION_PLANS


def _find_plan(plan: str) -> Optional[SubscriptionPlan]:
    return next((p for p in SUBSCRIPTION_PLANS if p.plan == plan), None)


async def get_status(db: AsyncSession, user: User) -> SubscriptionStatus:
    current = await crud.subscription.get_current_active_subscription(db, user.id, _now())
    if not current:
        return SubscriptionStatus(is_active=False)
    return SubscriptionStatus(is_active=True, plan=current.plan, expires_at=current.expires_at)


async def has_active_subscription(db: AsyncSession, user_id: int) -> bool:
    current = await crud.subscription.get_current_active_subscription(db, user_id, _now())
    return current is not None


async def list_subscriptions(db: AsyncSession, user: User, skip: int = 0, limit: int = 50) -> List[Subscription]:
    return await crud.subscription.get_subscriptions(db, user.id, skip, limit)


async def initiate(
    db: AsyncSession, user: User, request_in: InitializeSubscriptionRequest
) -> InitializeSubscriptionResponse:
    """Starts a subscription purchase. The browser gets redirected to the returned
    authorization_url to actually pay; nothing is activated until verify() confirms it."""
    if not settings.PAYSTACK_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments aren't configured yet. Try again later."
        )

    plan = _find_plan(request_in.plan)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan.")

    reference = f"sub-{uuid.uuid4().hex}"
    await crud.subscription.create_subscription(
        db, user_id=user.id, plan=plan.plan, ghs_amount=plan.ghs_amount, provider_ref=reference
    )

    try:
        result = await paystack_client.initialize_transaction(
            email=user.email,
            amount_ghs=plan.ghs_amount,
            reference=reference,
            callback_url=f"{settings.FRONTEND_BASE_URL}/subscribe/callback"
        )
    except paystack_client.PaystackError as e:
        logger.error(f"Failed to initialize subscription payment for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't start the payment. Try again in a moment."
        )

    return InitializeSubscriptionResponse(authorization_url=result["authorization_url"], reference=reference)


async def verify(db: AsyncSession, user: User, reference: str) -> Subscription:
    """Confirms a payment server-side (never trust the client's word that it succeeded) and
    activates the subscription - extending the current period if one's still active, or
    starting fresh from now otherwise."""
    subscription = await crud.subscription.get_subscription_by_reference(db, reference)
    if not subscription or subscription.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription payment not found.")

    if subscription.status == "active":
        return subscription  # already verified (e.g. the callback page re-fetched) - no-op

    try:
        payment_status = await paystack_client.verify_transaction(reference)
    except paystack_client.PaystackError as e:
        logger.error(f"Failed to verify subscription payment {reference}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't confirm the payment right now. Try again shortly."
        )

    if payment_status != "success":
        subscription.status = "failed"
        subscription = await crud.subscription.save_subscription(db, subscription)
        logger.info(f"Subscription payment {reference} did not succeed (status={payment_status}).")
        return subscription

    plan = _find_plan(subscription.plan)
    now = _now()
    current = await crud.subscription.get_current_active_subscription(db, user.id, now)
    period_start = _aware(current.expires_at) if current else now

    subscription.status = "active"
    subscription.started_at = now
    subscription.expires_at = period_start + timedelta(days=plan.duration_days)
    subscription = await crud.subscription.save_subscription(db, subscription)

    logger.info(f"Activated {subscription.plan} subscription for user {user.id}, expires {subscription.expires_at}.")
    return subscription
