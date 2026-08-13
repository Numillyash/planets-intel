from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.combat_state import CombatStateResponse, CombatStateUpsertRequest
from app.schemas.combined_intel import CombinedPrivateIntelResponse
from app.schemas.private_intel import LatestPrivateIntelResponse
from app.services.combat_events import get_combat_events
from app.services.combat_state import upsert_combat_state
from app.services.event_results import apply_structured_host_evidence
from app.services.historical_intel import (
    backfill_historical_turn,
    get_combined_private_intel_turn,
)
from app.services.historical_status import historical_intel_status
from app.services.historical_tracks import get_historical_ship_tracks
from app.services.host_events import get_accessible_host_events
from app.services.loadout_inference import get_ship_loadout_inference
from app.services.player_activity import get_player_activity_analysis
from app.services.private_intel import get_private_intel_turn
from app.services.threat_analysis import get_ship_threat_analysis


router = APIRouter()


@router.get(
    "/games/{game_id}/private-intel/history/turn/{turn}",
    response_model=LatestPrivateIntelResponse,
)
def historical_private_intel_turn(
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> LatestPrivateIntelResponse:
    result = get_private_intel_turn(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Historical private intelligence snapshot not found",
        )
    return LatestPrivateIntelResponse(**result)


@router.get(
    "/games/{game_id}/private-intel/history/combined/{turn}",
    response_model=CombinedPrivateIntelResponse,
)
def historical_combined_private_intel_turn(
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> CombinedPrivateIntelResponse:
    result = get_combined_private_intel_turn(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Historical combined intelligence snapshot not found",
        )
    return CombinedPrivateIntelResponse(**result)


@router.get(
    "/games/{game_id}/private-intel/history/status",
)
def historical_private_intel_status(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = historical_intel_status(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Historical intelligence context not found",
        )
    return result


@router.get(
    "/games/{game_id}/private-intel/history/ship-tracks",
)
def historical_ship_tracks(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    through_turn: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_historical_ship_tracks(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        through_turn=through_turn,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Historical ship-track context not found",
        )
    return result


@router.get(
    "/games/{game_id}/private-intel/history/combat-events",
)
def historical_combat_events(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    turn: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_combat_events(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat-event context not found",
        )
    return apply_structured_host_evidence(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        result=result,
    )


@router.put(
    "/games/{game_id}/private-intel/history/combat-events/{turn}/{vcr_id}/ships/{ship_id}/post-combat-state",
    response_model=CombatStateResponse,
)
def save_post_combat_state(
    payload: CombatStateUpsertRequest,
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    vcr_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    user: AppUser = Depends(require_user),
) -> CombatStateResponse:
    result = upsert_combat_state(
        user_id=user.id,
        game_id=game_id,
        turn=turn,
        vcr_id=vcr_id,
        ship_id=ship_id,
        post_combat_torpedoes=payload.post_combat_torpedoes,
        post_combat_fighters=payload.post_combat_fighters,
        note=payload.note,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accessible VCR ship not found",
        )
    return CombatStateResponse(**result)


@router.get(
    "/games/{game_id}/private-intel/history/host-events",
)
def historical_host_events(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    turn: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_accessible_host_events(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host-event context not found",
        )
    return result


@router.get(
    "/games/{game_id}/activity",
)
def player_activity_analysis(
    game_id: int = Path(gt=0),
    through_turn: int | None = Query(default=None, gt=0),
    _user: AppUser = Depends(require_user),
) -> dict[str, object]:
    return get_player_activity_analysis(
        game_id=game_id,
        through_turn=through_turn,
    )


@router.get(
    "/games/{game_id}/private-intel/analysis/ship-threat/{ship_id}",
)
def ship_threat_analysis(
    game_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    turn: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_ship_threat_analysis(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        ship_id=ship_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat-analysis context not found",
        )
    return result


@router.get(
    "/games/{game_id}/private-intel/analysis/loadout/{ship_id}",
)
def ship_loadout_inference(
    game_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    turn: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    result = get_ship_loadout_inference(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        ship_id=ship_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loadout-inference context not found",
        )
    return result


@router.post(
    "/games/{game_id}/private-intel/history/backfill/{turn}",
)
async def backfill_private_intel_turn(
    game_id: int = Path(gt=0),
    turn: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    try:
        return await backfill_historical_turn(
            user_id=user.id,
            game_id=game_id,
            linked_account_id=linked_account_id,
            turn=turn,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
