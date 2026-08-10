from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
)

from app.schemas.scores import ScoreHistoryResponse
from app.services.score_history import get_score_history


router = APIRouter()


@router.get(
    "/games/{game_id}/scores/history",
    response_model=ScoreHistoryResponse,
)
def score_history(
    game_id: int = Path(gt=0),
    slot_id: int | None = Query(
        default=None,
        gt=0,
    ),
    from_turn: int | None = Query(
        default=None,
        ge=1,
    ),
    to_turn: int | None = Query(
        default=None,
        ge=1,
    ),
) -> ScoreHistoryResponse:
    if (
        from_turn is not None
        and to_turn is not None
        and from_turn > to_turn
    ):
        raise HTTPException(
            status_code=422,
            detail="from_turn must not exceed to_turn",
        )

    result = get_score_history(
        game_id=game_id,
        slot_id=slot_id,
        from_turn=from_turn,
        to_turn=to_turn,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Game is not present in the local "
                "intelligence database"
            ),
        )

    return ScoreHistoryResponse(
        **result,
    )
