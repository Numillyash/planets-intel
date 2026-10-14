from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PrivateIntelObserver(BaseModel):
    linked_account_id: int
    planets_account_id: int | None
    planets_username: str
    player_slot_id: int
    is_active: bool


class PrivateIntelObservationMetadata(BaseModel):
    batch_id: int
    source: str
    snapshot_hash: str
    observed_at: datetime


class PrivateIntelCounts(BaseModel):
    planets: int
    ships: int
    starbases: int
    nebulas: int = 0
    ion_storms: int = 0
    star_clusters: int = 0
    minefields: int = 0


class PlanetObservationResponse(BaseModel):
    planet_id: int
    owner_id: int | None
    info_turn: int | None
    name: str | None
    x: int | None
    y: int | None
    payload: dict[str, Any]


class ShipObservationResponse(BaseModel):
    ship_id: int
    owner_id: int | None
    info_turn: int | None
    hull_id: int | None
    name: str | None
    x: int | None
    y: int | None
    warp: int | None
    payload: dict[str, Any]


class StarbaseObservationResponse(BaseModel):
    starbase_id: int
    planet_id: int | None
    race_id: int | None
    info_turn: int | None
    payload: dict[str, Any]


class StellarCartographyObservationResponse(BaseModel):
    feature_type: Literal[
        "nebula",
        "ion_storm",
        "star_cluster",
        "minefield",
    ]
    feature_id: int
    name: str | None
    info_turn: int | None
    x: int | None
    y: int | None
    radius: int | None
    payload: dict[str, Any]


class LatestPrivateIntelResponse(BaseModel):
    game_id: int
    turn: int

    observer: PrivateIntelObserver
    observation: PrivateIntelObservationMetadata
    counts: PrivateIntelCounts

    planets: list[PlanetObservationResponse]
    ships: list[ShipObservationResponse]
    starbases: list[StarbaseObservationResponse]
    stellar_cartography: list[
        StellarCartographyObservationResponse
    ] = Field(default_factory=list)
