from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.private_intel import (
    PlanetObservationResponse,
    PrivateIntelCounts,
    PrivateIntelObserver,
    ShipObservationResponse,
    StarbaseObservationResponse,
    StellarCartographyObservationResponse,
)


class CombinedIntelSource(BaseModel):
    linked_account_id: int
    planets_account_id: int | None
    planets_username: str
    player_slot_id: int
    batch_id: int
    turn: int
    source: str
    observed_at: datetime


class CombinedIntelEntityProvenance(BaseModel):
    linked_account_id: int
    planets_username: str
    player_slot_id: int
    batch_id: int
    batch_turn: int
    info_turn: int | None
    observed_at: datetime


class CombinedPlanetObservationResponse(PlanetObservationResponse):
    selected_source_linked_account_id: int
    field_sources: dict[str, int]
    provenance: list[CombinedIntelEntityProvenance]


class CombinedShipObservationResponse(ShipObservationResponse):
    selected_source_linked_account_id: int
    field_sources: dict[str, int]
    provenance: list[CombinedIntelEntityProvenance]


class CombinedStarbaseObservationResponse(StarbaseObservationResponse):
    selected_source_linked_account_id: int
    field_sources: dict[str, int]
    provenance: list[CombinedIntelEntityProvenance]


class CombinedStellarCartographyObservationResponse(
    StellarCartographyObservationResponse
):
    selected_source_linked_account_id: int
    field_sources: dict[str, int]
    provenance: list[CombinedIntelEntityProvenance]


class CombinedPrivateIntelResponse(BaseModel):
    mode: Literal["combined"] = "combined"
    aggregation_policy: Literal["freshest_field_union"] = (
        "freshest_field_union"
    )

    game_id: int
    turn: int
    primary_observer: PrivateIntelObserver
    sources: list[CombinedIntelSource]
    counts: PrivateIntelCounts

    planets: list[CombinedPlanetObservationResponse]
    ships: list[CombinedShipObservationResponse]
    starbases: list[CombinedStarbaseObservationResponse]
    stellar_cartography: list[
        CombinedStellarCartographyObservationResponse
    ]
