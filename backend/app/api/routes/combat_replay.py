from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.combat_planner import (
    BattleSimulatorOddsRequest,
    BattleSimulatorRunRequest,
    CombatPlannerRepeatRequest,
    CombatPlannerScenarioRequest,
)
from app.services.battle_simulator import (
    run_battle_simulator_odds,
    run_battle_simulator_once,
)
from app.services.combat_replay_sampling import get_combat_replay_repeat_odds
from app.services.combat_replay_trace import (
    get_combat_replay_odds,
    get_combat_replay_scenario,
    get_combat_replay_trace,
)


router = APIRouter()


@router.get(
    "/games/{game_id}/private-intel/history/combat-events/{turn}/{vcr_id}/replay",
)
def combat_replay_trace(
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    vcr_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_combat_replay_trace(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accessible VCR replay not found",
        )
    return result


@router.post(
    "/games/{game_id}/private-intel/history/combat-events/{turn}/{vcr_id}/scenario",
)
def combat_replay_scenario(
    body: CombatPlannerScenarioRequest,
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    vcr_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_combat_replay_scenario(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
        left_overrides=body.left.model_dump(),
        right_overrides=body.right.model_dump(),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accessible VCR scenario source not found",
        )
    return result


@router.post(
    "/games/{game_id}/private-intel/history/combat-events/{turn}/{vcr_id}/odds",
)
def combat_replay_odds(
    body: CombatPlannerScenarioRequest,
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    vcr_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    """Exhaustive 118-start-seed series used for validation/series mode."""
    result = get_combat_replay_odds(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
        left_overrides=body.left.model_dump(),
        right_overrides=body.right.model_dump(),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accessible VCR odds source not found",
        )
    return result


@router.post(
    "/games/{game_id}/private-intel/history/combat-events/{turn}/{vcr_id}/repeat-odds",
)
def combat_replay_repeat_odds(
    body: CombatPlannerRepeatRequest,
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    vcr_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_combat_replay_repeat_odds(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
        left_overrides=body.left.model_dump(),
        right_overrides=body.right.model_dump(),
        battles=body.battles,
        sampling_seed=body.sampling_seed,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accessible VCR repeated-simulation source not found",
        )
    return result


@router.post("/games/{game_id}/battle-simulator/run")
def standalone_battle_simulator_run(
    body: BattleSimulatorRunRequest,
    game_id: int = Path(gt=0),
    _user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = run_battle_simulator_once(
        game_id=game_id,
        left=body.left.model_dump(),
        right=body.right.model_dump(),
        seed=body.seed,
        right_balance_bonus=body.right_balance_bonus,
        sampling_seed=body.sampling_seed,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game combat rule catalog not found",
        )
    return result


@router.post("/games/{game_id}/battle-simulator/odds")
def standalone_battle_simulator_odds(
    body: BattleSimulatorOddsRequest,
    game_id: int = Path(gt=0),
    _user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = run_battle_simulator_odds(
        game_id=game_id,
        left=body.left.model_dump(),
        right=body.right.model_dump(),
        battles=body.battles,
        sampling_seed=body.sampling_seed,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game combat rule catalog not found",
        )
    return result
