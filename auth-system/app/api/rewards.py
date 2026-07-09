import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.reward import BalanceResponse, LedgerEntryResponse, RedeemRequest, RedemptionResponse, RedemptionTier
from app.services import reward as reward_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.get("/redemption-tiers", response_model=List[RedemptionTier])
async def get_redemption_tiers():
    """List the fixed MoMo cash denominations available for redemption and their KP cost."""
    return reward_service.get_redemption_tiers()


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve the current user's all-time reward point balance."""
    points = await reward_service.get_balance(db, current_user)
    return BalanceResponse(points=points)


@router.get("/ledger", response_model=List[LedgerEntryResponse])
async def get_ledger(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List the current user's point transaction history, most recent first."""
    return await reward_service.list_ledger(db, current_user, skip, limit)


@router.post("/redeem", response_model=RedemptionResponse, status_code=status.HTTP_201_CREATED)
async def redeem_points(
    redeem_in: RedeemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Redeem points for MoMo cash (phase 1 - the only redemption type supported)."""
    return await reward_service.redeem(db, current_user, redeem_in)


@router.get("/redemptions", response_model=List[RedemptionResponse])
async def get_redemptions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List the current user's past redemptions, most recent first."""
    return await reward_service.list_redemptions(db, current_user, skip, limit)
