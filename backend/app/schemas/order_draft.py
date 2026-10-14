from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


MovementMode = Literal["waypoint", "intercept"]
StarbasePrimaryOrder = Literal[
    "none",
    "refuel",
    "max_defense",
    "load_torpedoes",
    "unload_freighters",
    "repair_base",
    "force_surrender",
]


FORBIDDEN_FRIENDLY_CODE_CHARS = frozenset({"&", "<", ">"})


def validate_friendly_code(value: str) -> str:
    if len(value) > 3:
        raise ValueError("friendly code may contain at most three characters")
    if any(char in FORBIDDEN_FRIENDLY_CODE_CHARS for char in value):
        raise ValueError("friendly code may not contain &, < or >")
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("friendly code must contain printable ASCII characters")
    return value


class ShipOrderDraftUpsertRequest(BaseModel):
    warp: int | None = Field(default=None, ge=0, le=9)
    waypoint_x: int | None = None
    waypoint_y: int | None = None
    movement_mode: MovementMode | None = None
    intercept_target_ship_id: int | None = Field(default=None, gt=0)
    tow_target_ship_id: int | None = Field(default=None, gt=0)
    friendly_code: str | None = None
    mission: str | None = Field(default=None, min_length=1, max_length=80)
    primary_enemy_id: int | None = Field(default=None, ge=0, le=99)

    @field_validator("friendly_code")
    @classmethod
    def friendly_code_is_valid(cls, value: str | None) -> str | None:
        return validate_friendly_code(value) if value is not None else None

    @model_validator(mode="after")
    def validate_order(self) -> "ShipOrderDraftUpsertRequest":
        if (self.waypoint_x is None) != (self.waypoint_y is None):
            raise ValueError("waypoint_x and waypoint_y must be supplied together")

        if self.movement_mode == "intercept" and self.intercept_target_ship_id is None:
            raise ValueError("intercept movement requires intercept_target_ship_id")

        if (
            self.intercept_target_ship_id is not None
            and self.movement_mode != "intercept"
        ):
            raise ValueError("intercept_target_ship_id requires intercept movement")

        if self.tow_target_ship_id is not None and self.movement_mode == "intercept":
            raise ValueError("tow_target_ship_id cannot be combined with intercept movement")

        if not self.model_fields_set:
            raise ValueError("at least one draft order must be supplied")
        return self


class ShipOrderDraftResponse(BaseModel):
    game_id: int
    linked_account_id: int
    turn: int
    ship_id: int
    base_batch_id: int
    base_snapshot_hash: str
    stale: bool

    upstream_warp: int | None
    upstream_waypoint_x: int | None
    upstream_waypoint_y: int | None
    upstream_friendly_code: str | None
    upstream_mission: str | None
    upstream_primary_enemy_id: int | None
    upstream_tow_target_ship_id: int | None

    warp: int | None
    waypoint_x: int | None
    waypoint_y: int | None
    movement_mode: MovementMode
    intercept_target_ship_id: int | None
    tow_target_ship_id: int | None
    friendly_code: str | None
    mission: str | None
    primary_enemy_id: int | None

    changed_warp: bool
    changed_waypoint: bool
    changed_movement: bool
    changed_tow_target: bool
    changed_friendly_code: bool
    changed_mission: bool
    changed_primary_enemy: bool
    source: str = "local_order_draft"


class PlanetOrderDraftUpsertRequest(BaseModel):
    friendly_code: str

    @field_validator("friendly_code")
    @classmethod
    def friendly_code_is_valid(cls, value: str) -> str:
        return validate_friendly_code(value)


class PlanetOrderDraftResponse(BaseModel):
    game_id: int
    linked_account_id: int
    turn: int
    planet_id: int
    base_batch_id: int
    base_snapshot_hash: str
    stale: bool
    upstream_friendly_code: str | None
    friendly_code: str | None
    changed_friendly_code: bool
    source: str = "local_order_draft"


class StarbaseOrderDraftUpsertRequest(BaseModel):
    primary_order: StarbasePrimaryOrder


class StarbaseOrderDraftResponse(BaseModel):
    game_id: int
    linked_account_id: int
    turn: int
    starbase_id: int
    planet_id: int
    base_batch_id: int
    base_snapshot_hash: str
    stale: bool
    upstream_primary_order: str | None
    primary_order: StarbasePrimaryOrder
    changed_primary_order: bool
    source: str = "local_order_draft"
