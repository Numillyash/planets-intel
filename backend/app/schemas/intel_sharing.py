from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DashboardIntelShareRequest(BaseModel):
    source_account_id: int = Field(gt=0)
    target_planets_username: str = Field(
        min_length=1,
        max_length=255,
    )


class DashboardIntelShareDecision(BaseModel):
    account_id: int = Field(gt=0)


class DashboardIntelShareAccount(BaseModel):
    linked_account_id: int
    planets_username: str
    is_mine: bool
    is_active: bool
    approved: bool


class DashboardIntelShareResponse(BaseModel):
    id: int
    status: Literal["pending", "active"]
    account_a: DashboardIntelShareAccount
    account_b: DashboardIntelShareAccount
    created_at: datetime
    updated_at: datetime


class DashboardIntelSharesResponse(BaseModel):
    shares: list[DashboardIntelShareResponse]


class DashboardIntelShareRevokeResponse(BaseModel):
    success: bool
