from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.planetsnu.client import PlanetsNuError
from app.schemas.account_games import (
    AccountGamesResponse,
)
from app.services.account_games import (
    get_account_games,
)


router = APIRouter()


@router.get(
    "/planets/accounts/{account_id}/games",
    response_model=AccountGamesResponse,
)
async def account_games(
    account_id: int = Path(gt=0),
    user: AppUser = Depends(
        require_user
    ),
) -> AccountGamesResponse:
    try:
        result = await get_account_games(
            user_id=user.id,
            linked_account_id=account_id,
        )
    except PlanetsNuError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "Planets.nu game list "
                "is unavailable"
            ),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Linked Planets.nu account "
                "not found"
            ),
        )

    return AccountGamesResponse(
        **result
    )
