from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Plan = Literal["monthly", "quarterly", "annual"]


class SubscriptionPlan(BaseModel):
    plan: Plan
    ghs_amount: int
    duration_days: int


class SubscriptionStatus(BaseModel):
    is_active: bool
    plan: Optional[str] = None
    expires_at: Optional[datetime] = None


class InitializeSubscriptionRequest(BaseModel):
    plan: Plan = Field(..., description="Which subscription plan to purchase")


class InitializeSubscriptionResponse(BaseModel):
    authorization_url: str
    reference: str


class VerifySubscriptionRequest(BaseModel):
    reference: str


class SubscriptionResponse(BaseModel):
    id: int
    plan: str
    ghs_amount: int
    status: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
