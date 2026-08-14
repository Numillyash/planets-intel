from typing import Literal

from pydantic import BaseModel, Field, model_validator


MovementMode = Literal["waypoint", "intercept"]


class ShipOrderDraftUpsertRequest(BaseModel):
    warp: int | None = Field(default=None, ge=0, le=9)
    waypoint_x: int | None = None
    waypoint_y: int | None = None
    movement_mode: MovementMode | None = None
    intercept_target_ship_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> "ShipOrderDraftUpsertRequest":
        if (self.waypoint_x is None) != (self.waypoint_y is None):
            raise ValueError("waypoint_x and waypoint_y must be supplied together")

        if self.movement_mode == "intercept" and self.intercept_target_ship_id is None:
            raise ValueError("intercept movement requires intercept_target_ship_id")

        if (
            self.intercept_target_ship_id is not None
            and self.movement_mode not in (None, "intercept")
        ):
            raise ValueError("intercept_target_ship_id requires intercept movement")

        if (
            self.warp is None
            and self.waypoint_x is None
            and self.movement_mode is None
            and self.intercept_target_ship_id is None
        ):
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

    warp: int | None
    waypoint_x: int | None
    waypoint_y: int | None
    movement_mode: MovementMode
    intercept_target_ship_id: int | None

    changed_warp: bool
    changed_waypoint: bool
    changed_movement: bool
    source: str = "local_order_draft"
