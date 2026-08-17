from typing import Literal

from pydantic import BaseModel, Field


RightBalanceMode = Literal["auto", "on", "off"]


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


class BattleSimulatorCombatant(BaseModel):
    """Materialized simulation-only combatant.

    ``physical_*`` fields describe installed weapons before damage/racial
    modifiers. ``*_count`` fields are the effective values for the first
    engagement. Sequence simulation uses physical counts to recompute the
    surviving ship's functional weapons after each fight.
    """

    source_kind: Literal["known_ship", "known_planet", "vcr", "manual"]
    source_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, max_length=255)
    object_id: int | None = Field(default=None, gt=0)
    owner_id: int | None = Field(default=None, ge=0)
    race_id: int | None = Field(default=None, ge=0)
    hull_id: int = Field(ge=0)
    has_starbase: bool = False

    physical_beam_count: int | None = Field(default=None, ge=0, le=10)
    physical_launcher_count: int | None = Field(default=None, ge=0, le=10)
    physical_bay_count: int | None = Field(default=None, ge=0, le=30)
    federation_crew_bonus: bool = False

    beam_count: int = Field(ge=0, le=10)
    launcher_count: int = Field(ge=0, le=10)
    bay_count: int = Field(ge=0, le=33)
    beam_id: int = Field(ge=0)
    torpedo_id: int = Field(ge=0)
    shield: int = Field(ge=0, le=100)
    damage: int = Field(ge=0, le=9999)
    crew: int = Field(ge=0, le=100_000)
    mass: int = Field(gt=0, le=100_000)
    torpedoes: int = Field(ge=0, le=100_000)
    fighters: int = Field(ge=0, le=100_000)
    beam_kill_rate: int = Field(default=1, ge=1, le=10)
    beam_charge_rate: int = Field(default=1, ge=1, le=20)
    torp_charge_rate: int = Field(default=1, ge=1, le=20)
    torp_miss_rate: int = Field(default=35, ge=0, le=100)
    crew_defense_rate: int = Field(default=0, ge=0, le=100)
    notes: list[str] = Field(default_factory=list, max_length=32)


class BattleSimulatorRunRequest(BaseModel):
    left: BattleSimulatorCombatant
    right: BattleSimulatorCombatant
    seed: int = Field(default=1, ge=1, le=118)
    right_balance_bonus: RightBalanceMode = "auto"
    sampling_seed: int | None = Field(default=None, ge=0, le=2**63 - 1)


class BattleSimulatorOddsRequest(BaseModel):
    left: BattleSimulatorCombatant
    right: BattleSimulatorCombatant
    battles: int = Field(default=10_000, ge=1, le=100_000)
    right_balance_bonus: RightBalanceMode = "auto"
    sampling_seed: int | None = Field(default=None, ge=0, le=2**63 - 1)


class BattleSimulatorSequenceRunRequest(BaseModel):
    left: list[BattleSimulatorCombatant] = Field(min_length=1, max_length=20)
    right: list[BattleSimulatorCombatant] = Field(min_length=1, max_length=20)
    seed: int = Field(default=1, ge=1, le=118)
    right_balance_bonus: RightBalanceMode = "auto"
    sampling_seed: int | None = Field(default=None, ge=0, le=2**63 - 1)


class BattleSimulatorSequenceOddsRequest(BaseModel):
    left: list[BattleSimulatorCombatant] = Field(min_length=1, max_length=20)
    right: list[BattleSimulatorCombatant] = Field(min_length=1, max_length=20)
    battles: int = Field(default=10_000, ge=1, le=100_000)
    right_balance_bonus: RightBalanceMode = "auto"
    sampling_seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
