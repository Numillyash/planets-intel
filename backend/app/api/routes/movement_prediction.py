from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.movement_prediction import DraftMovementPredictionResponse
from app.services.movement_prediction_runtime import (
    MovementPredictionAccessError,
    MovementPredictionNotFound,
    get_draft_movement_prediction,
)


router = APIRouter()


@router.get(
    "/games/{game_id}/movement-prediction",
    response_model=DraftMovementPredictionResponse,
)
def movement_prediction(
    game_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> DraftMovementPredictionResponse:
    try:
        result = get_draft_movement_prediction(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
        )
    except MovementPredictionAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except MovementPredictionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return DraftMovementPredictionResponse(**result)
