from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.subscription import Subscription


async def create_subscription(
    db: AsyncSession, user_id: int, plan: str, ghs_amount: int, provider_ref: str
) -> Subscription:
    """Records a purchase attempt as 'pending' - it only becomes 'active' once the payment
    is verified server-side (see app.services.subscription.verify_and_activate)."""
    subscription = Subscription(
        user_id=user_id, plan=plan, ghs_amount=ghs_amount, provider_ref=provider_ref, status="pending"
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def get_subscription_by_reference(db: AsyncSession, provider_ref: str) -> Optional[Subscription]:
    result = await db.execute(select(Subscription).where(Subscription.provider_ref == provider_ref))
    return result.scalar_one_or_none()


async def get_current_active_subscription(db: AsyncSession, user_id: int, now: datetime) -> Optional[Subscription]:
    """The most recent row that's paid and not yet expired - or None if the user has no
    active subscription (never subscribed, it lapsed, or the last attempt failed)."""
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_subscriptions(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 50) -> List[Subscription]:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def save_subscription(db: AsyncSession, subscription: Subscription) -> Subscription:
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription
