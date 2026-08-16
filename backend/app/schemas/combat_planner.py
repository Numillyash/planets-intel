from pydantic import BaseModel, Field


class CombatPlannerSideOverrides(BaseModel):
    fighters: int | None = Field(default=None, ge=0, le=100_000)
    torpedoes: int | None = Field(default=None, ge=0, le=100_000)


class CombatPlannerScenarioRequest(BaseModel):
    left: CombatPlannerSideOverrides = Field(
        default_factory=CombatPlannerSideOverrides,
    )
    right: CombatPlannerSideOverrides = Field(
        default_factory=CombatPlannerSideOverrides,
    )
