from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.game_activity import GameActivityResponse
from app.services.game_activity import get_owned_game_activity


router = APIRouter()


@router.get(
    "/games/{game_id}/communications",
    response_model=GameActivityResponse,
)
def game_communications(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    limit: int = Query(default=500, ge=1, le=2000),
    user: AppUser = Depends(require_user),
) -> GameActivityResponse:
    result = get_owned_game_activity(
        user_id=user.id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        limit=limit,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked Planets.nu account not found",
        )
    return GameActivityResponse(**result)
