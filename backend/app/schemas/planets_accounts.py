from datetime import datetime

from pydantic import BaseModel, Field


class LinkPlanetsAccountRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=255,
    )

    password: str = Field(
        min_length=1,
        max_length=1024,
    )


class PlanetsAccountResponse(BaseModel):
    id: int
    planets_username: str
    planets_account_id: int | None
    is_active: bool

    last_verified_at: datetime | None
    last_error: str | None


class PlanetsAccountsResponse(BaseModel):
    accounts: list[PlanetsAccountResponse]


class UnlinkPlanetsAccountResponse(BaseModel):
    success: bool
