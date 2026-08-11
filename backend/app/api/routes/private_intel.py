from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.private_intel import (
    LatestPrivateIntelResponse,
)
from app.services.private_intel import (
    get_latest_private_intel,
)


router = APIRouter()


@router.get(
    "/games/{game_id}/private-intel/latest",
    response_model=LatestPrivateIntelResponse,
)
def latest_private_intel(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(
        require_user
    ),
) -> LatestPrivateIntelResponse:
    result = get_latest_private_intel(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=(
            linked_account_id
        ),
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Private intelligence snapshot "
                "not found"
            ),
        )

    return LatestPrivateIntelResponse(
        **result
    )
