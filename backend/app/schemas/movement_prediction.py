from typing import Literal

from pydantic import BaseModel


PredictionPhase = Literal["move_most", "intercept"]
PredictionMode = Literal["waypoint", "intercept"]


class ShipMovementPrediction(BaseModel):
    ship_id: int
    movement_mode: PredictionMode
    phase: PredictionPhase
    status: str
    certain: bool
    start_x: float | None
    start_y: float | None
    waypoint_x: float | None
    waypoint_y: float | None
    target_ship_id: int | None
    target_x: float | None
    target_y: float | None
    predicted_x: float | None
    predicted_y: float | None
    requested_distance: float | None
    max_distance: float | None
    moved_distance: float | None
    warp: int | None
    speed_multiplier: float
    reason: str
    warnings: list[str]


class DraftMovementPredictionResponse(BaseModel):
    game_id: int
    linked_account_id: int
    turn: int
    intercept_mode: Literal["classic", "chained"]
    basis: Literal["local_order_drafts_geometry"] = "local_order_drafts_geometry"
    host_final: bool = False
    items: list[ShipMovementPrediction]
