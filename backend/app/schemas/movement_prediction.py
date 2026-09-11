from typing import Literal

from pydantic import BaseModel


PredictionPhase = Literal["tow", "move_most", "intercept"]
PredictionMode = Literal["tow", "waypoint", "intercept"]
TowRole = Literal["tower", "target"]
PredictionBlockerClass = Literal[
    "phase_state_required",
    "implementation_gap",
    "missing_fact",
    "dependency_unresolved",
    "order_ambiguity",
    "unsupported_host_rule",
]


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
    target_warp: int | None
    target_speed_multiplier: float | None
    target_standard_max_distance: float | None
    pre_well_x: float | None
    pre_well_y: float | None
    warp_well_status: str | None
    warp_well_planet_id: int | None
    warp_well_planet_name: str | None
    warp_well_pull_distance: float | None
    predicted_x: float | None
    predicted_y: float | None
    requested_distance: float | None
    max_distance: float | None
    moved_distance: float | None
    displacement_distance: float | None
    warp: int | None
    speed_multiplier: float
    fuel_status: str = "not_evaluated"
    movement_mass: int | None = None
    fuel_available: int | None = None
    fuel_factor: int | None = None
    fuel_required: int | None = None
    fuel_used: int | None = None
    fuel_limited: bool | None = None
    fuel_basis: str = "not_evaluated"
    fuel_reason: str = "Fuel evaluation was not available for this movement item."
    tow_role: TowRole | None = None
    tow_tower_ship_id: int | None = None
    tow_target_ship_id: int | None = None
    tow_lock_status: str | None = None
    blocker_class: PredictionBlockerClass | None = None
    blocker_reason: str | None = None
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
