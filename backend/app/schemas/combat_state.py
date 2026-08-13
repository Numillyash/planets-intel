from pydantic import BaseModel, Field


class CombatStateUpsertRequest(BaseModel):
    post_combat_torpedoes: int | None = Field(default=None, ge=0)
    post_combat_fighters: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=256)


class CombatStateResponse(BaseModel):
    game_id: int
    turn: int
    vcr_id: int
    ship_id: int
    post_combat_torpedoes: int | None
    post_combat_fighters: int | None
    note: str | None
    source: str = "analyst_confirmed_vcr_review"
