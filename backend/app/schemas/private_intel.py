from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


class LatestPrivateIntelResponse(BaseModel):
    game_id: int
    turn: int

    observer: PrivateIntelObserver
    observation: PrivateIntelObservationMetadata
    counts: PrivateIntelCounts

    planets: list[PlanetObservationResponse]
    ships: list[ShipObservationResponse]
    starbases: list[StarbaseObservationResponse]
