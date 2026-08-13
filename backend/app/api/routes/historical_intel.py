from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.combined_intel import CombinedPrivateIntelResponse
from app.schemas.private_intel import LatestPrivateIntelResponse
from app.services.combat_events import get_combat_events
from app.services.historical_intel import (
    backfill_historical_turn,
    get_combined_private_intel_turn,
)
from app.services.historical_status import historical_intel_status
from app.services.historical_tracks import get_historical_ship_tracks
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
    return result


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
