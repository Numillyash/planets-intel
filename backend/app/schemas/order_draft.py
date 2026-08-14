from pydantic import BaseModel, Field, model_validator


class ShipOrderDraftUpsertRequest(BaseModel):
    warp: int | None = Field(default=None, ge=0, le=9)
    waypoint_x: int | None = None
    waypoint_y: int | None = None

    @model_validator(mode="after")
    def validate_waypoint_pair(self) -> "ShipOrderDraftUpsertRequest":
        if (self.waypoint_x is None) != (self.waypoint_y is None):
            raise ValueError("waypoint_x and waypoint_y must be supplied together")
        if self.warp is None and self.waypoint_x is None:
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

    changed_warp: bool
    changed_waypoint: bool
    source: str = "local_order_draft"
