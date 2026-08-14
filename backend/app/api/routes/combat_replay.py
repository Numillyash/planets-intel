from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.services.combat_replay_trace import get_combat_replay_trace


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
