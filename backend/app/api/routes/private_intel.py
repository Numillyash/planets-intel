import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy import select

from app.api.dependencies.auth import require_user
from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.models.user import AppUser
from app.planetsnu.client import PlanetsNuError
from app.schemas.combined_intel import CombinedPrivateIntelResponse
from app.schemas.private_intel import LatestPrivateIntelResponse
from app.services.combined_intel import get_combined_private_intel
from app.services.private_intel import get_latest_private_intel
from app.services.private_sync import (
    PrivateSyncError,
    PrivateSyncTransportError,
    sync_private_game,
)
from app.services.public_sync import sync_public_game


router = APIRouter()


def _latest_or_none(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict | None:
    return get_latest_private_intel(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )


@router.get(
    "/games/{game_id}/private-intel/latest",
    response_model=LatestPrivateIntelResponse,
)
def latest_private_intel(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> LatestPrivateIntelResponse:
    result = _latest_or_none(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Private intelligence snapshot not found",
        )

    return LatestPrivateIntelResponse(**result)


@router.post(
    "/games/{game_id}/private-intel/refresh",
    response_model=LatestPrivateIntelResponse,
)
async def refresh_private_intel(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> LatestPrivateIntelResponse:
    with SessionLocal() as session:
        owned_account_id = session.execute(
            select(PlanetsAccount.id).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user.id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

    if owned_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked Planets.nu account not found",
        )

    cached = _latest_or_none(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )

    try:
        # Refresh canonical game/player state first so a newly selected game
        # can immediately accept its first private observation.
        await sync_public_game(game_id)
        await sync_private_game(
            linked_account_id=linked_account_id,
            game_id=game_id,
        )
    except PrivateSyncTransportError as exc:
        if cached is not None:
            return LatestPrivateIntelResponse(**cached)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.TransportError as exc:
        if cached is not None:
            return LatestPrivateIntelResponse(**cached)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Planets.nu public synchronization transport failed "
                f"({type(exc).__name__})"
            ),
        ) from exc
    except PrivateSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PlanetsNuError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Planets.nu synchronization failed",
        ) from exc

    result = _latest_or_none(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Private intelligence refresh produced no snapshot",
        )

    return LatestPrivateIntelResponse(**result)


@router.get(
    "/games/{game_id}/private-intel/combined",
    response_model=CombinedPrivateIntelResponse,
)
def combined_private_intel(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> CombinedPrivateIntelResponse:
    result = get_combined_private_intel(
        user_id=user.id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Private intelligence snapshot not found",
        )

    return CombinedPrivateIntelResponse(**result)
