"""API for pending per-game consent evidence; not a sharing entitlement."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SharingMode = Literal["native", "unrestricted"]

DisclosureScope = Literal[
    "owned_unit_locations",
    "third_party_contacts",
    "combat_vcr_evidence",
    "owned_planet_details",
    "owned_ship_details",
]


class GameGrantRequest(BaseModel):
    grantor_account_id: int = Field(gt=0)
    grantee_planets_username: str = Field(min_length=1, max_length=255)
    requested_scopes: list[DisclosureScope] = Field(min_length=1, max_length=5)
    sharing_mode: SharingMode = "native"


class GameGrantConsent(BaseModel):
    grantee_account_id: int = Field(gt=0)
    # Must explicitly acknowledge unrestricted cross-player disclosure.
    confirm_unrestricted: bool = False


class GameGrantRevoke(BaseModel):
    account_id: int = Field(gt=0)


class GameGrantResponse(BaseModel):
    id: int
    game_id: int
    grantor_account_id: int
    grantee_account_id: int
    grantor_slot_id: int
    grantee_slot_id: int
    membership_verified_turn: int
    requested_scopes: list[DisclosureScope]
    sharing_mode: SharingMode
    expanded_disclosure_confirmed_at: datetime | None
    status: Literal["pending", "consented_pending_policy", "revoked"]
    authorizes_private_intel: Literal[False] = False
    consented_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GameGrantsResponse(BaseModel):
    grants: list[GameGrantResponse]
