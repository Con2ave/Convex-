import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionPlan,
    SubscriptionStatus,
    InitializeSubscriptionRequest,
    InitializeSubscriptionResponse,
    VerifySubscriptionRequest,
    SubscriptionResponse,
)
from app.services import subscription as subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_plans():
    """List the available subscription plans and their GHS price."""
    return subscription_service.list_plans()


@router.get("/status", response_model=SubscriptionStatus)
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Whether the current user has an active subscription right now, and until when."""
    return await subscription_service.get_status(db, current_user)


@router.post("/initialize", response_model=InitializeSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def initialize_subscription(
    request_in: InitializeSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Start a subscription purchase - returns a Paystack checkout URL to redirect to."""
    return await subscription_service.initiate(db, current_user, request_in)


@router.post("/verify", response_model=SubscriptionResponse)
async def verify_subscription(
    verify_in: VerifySubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Confirm a payment server-side and activate the subscription if it succeeded.
    Called from the frontend's Paystack callback page."""
    return await subscription_service.verify(db, current_user, verify_in.reference)


@router.get("/history", response_model=List[SubscriptionResponse])
async def get_history(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List the current user's past subscription purchases, most recent first."""
    return await subscription_service.list_subscriptions(db, current_user, skip, limit)
