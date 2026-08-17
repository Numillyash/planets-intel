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


class CombatPlannerRepeatRequest(CombatPlannerScenarioRequest):
    battles: int = Field(default=10_000, ge=1, le=100_000)
    sampling_seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
