from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

Network = Literal["mtn", "telecel", "airteltigo"]


class BalanceResponse(BaseModel):
    points: int


class LedgerEntryResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    points: int
    reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RedemptionTier(BaseModel):
    """A fixed MoMo cash denomination and its (deliberately non-linear) KP cost."""
    ghs_amount: int
    kp_cost: int


class RedeemRequest(BaseModel):
    ghs_amount: int = Field(..., description="Which redemption tier to redeem (must match an available tier)")
    recipient_phone: str = Field(
        ..., min_length=9, max_length=20, description="Mobile money number to receive the payout"
    )
    network: Network = Field(..., description="Mobile network the phone number is registered on")


class RedemptionResponse(BaseModel):
    id: int
    points_spent: int
    ghs_amount: int
    reward_type: str
    status: str
    provider_ref: Optional[str] = None
    recipient_phone: str
    network: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
