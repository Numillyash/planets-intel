from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)

from app.api.dependencies.auth import require_user
from app.models.planets_account import PlanetsAccount
from app.models.user import AppUser
from app.planetsnu.client import (
    PlanetsNuAuthError,
    PlanetsNuError,
)
from app.schemas.planets_accounts import (
    LinkPlanetsAccountRequest,
    PlanetsAccountResponse,
    PlanetsAccountsResponse,
    UnlinkPlanetsAccountResponse,
)
from app.services.planets_accounts import (
    link_planets_account,
    list_planets_accounts,
    unlink_planets_account,
)


router = APIRouter()


def account_response(
    account: PlanetsAccount,
) -> PlanetsAccountResponse:
    return PlanetsAccountResponse(
        id=account.id,
        planets_username=account.planets_username,
        planets_account_id=account.planets_account_id,
        is_active=account.is_active,
        last_verified_at=account.last_verified_at,
        last_error=account.last_error,
    )


@router.get(
    "/planets/accounts",
    response_model=PlanetsAccountsResponse,
)
def get_accounts(
    user: AppUser = Depends(
        require_user
    ),
) -> PlanetsAccountsResponse:
    accounts = list_planets_accounts(
        user.id
    )

    return PlanetsAccountsResponse(
        accounts=[
            account_response(account)
            for account in accounts
        ]
    )


@router.post(
    "/planets/accounts",
    response_model=PlanetsAccountResponse,
)
async def add_account(
    payload: LinkPlanetsAccountRequest,
    user: AppUser = Depends(
        require_user
    ),
) -> PlanetsAccountResponse:
    try:
        account = await link_planets_account(
            user_id=user.id,
            username=payload.username,
            password=payload.password,
        )

    except PlanetsNuAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Planets.nu username or password",
        ) from exc

    except PlanetsNuError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Planets.nu API is unavailable",
        ) from exc

    return account_response(
        account
    )


@router.delete(
    "/planets/accounts/{account_id}",
    response_model=UnlinkPlanetsAccountResponse,
)
def delete_account(
    account_id: int = Path(gt=0),
    user: AppUser = Depends(
        require_user
    ),
) -> UnlinkPlanetsAccountResponse:
    removed = unlink_planets_account(
        user_id=user.id,
        account_id=account_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked Planets.nu account not found",
        )

    return UnlinkPlanetsAccountResponse(
        success=True
    )
