"""Game-specific consent ledger; never a raw private-intel API."""
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.game_intel_grants import (
    GameGrantConsent, GameGrantRequest, GameGrantResponse,
    GameGrantRevoke, GameGrantsResponse,
)
from app.services.game_intel_grants import (
    GrantConflict, GrantForbidden, GrantNotFound,
    list_game_grants, request_game_grant, consent_game_grant, revoke_game_grant,
)

from app.services.game_intel_preview import preview_game_grant
from app.services.game_intel_read import get_received_game_intel
from fastapi import Response

router = APIRouter()


def _http_error(exc: Exception) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, GrantNotFound)
        else status.HTTP_403_FORBIDDEN if isinstance(exc, GrantForbidden)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/intel/games/{game_id}/grants", response_model=GameGrantsResponse)
def list_grants(game_id: int = Path(gt=0), user: AppUser = Depends(require_user)) -> GameGrantsResponse:
    return GameGrantsResponse(grants=list_game_grants(user_id=user.id, game_id=game_id))


@router.post("/intel/games/{game_id}/grants", response_model=GameGrantResponse, status_code=201)
def request_grant(
    payload: GameGrantRequest, game_id: int = Path(gt=0), user: AppUser = Depends(require_user),
) -> GameGrantResponse:
    try:
        record = request_game_grant(
            user_id=user.id, game_id=game_id,
            grantor_account_id=payload.grantor_account_id,
            grantee_planets_username=payload.grantee_planets_username,
            requested_scopes=list(payload.requested_scopes),
            sharing_mode=payload.sharing_mode,
        )
    except (GrantNotFound, GrantForbidden, GrantConflict) as exc:
        raise _http_error(exc) from exc
    return GameGrantResponse(**record)


@router.post("/intel/games/{game_id}/grants/{grant_id}/consent", response_model=GameGrantResponse)
def consent_grant(
    payload: GameGrantConsent, game_id: int = Path(gt=0),
    grant_id: int = Path(gt=0), user: AppUser = Depends(require_user),
) -> GameGrantResponse:
    try:
        record = consent_game_grant(
            user_id=user.id, game_id=game_id,
            grant_id=grant_id, grantee_account_id=payload.grantee_account_id,
            confirm_unrestricted=payload.confirm_unrestricted,
        )
    except (GrantNotFound, GrantForbidden, GrantConflict) as exc:
        raise _http_error(exc) from exc
    return GameGrantResponse(**record)


@router.post("/intel/games/{game_id}/grants/{grant_id}/revoke", response_model=GameGrantResponse)
def revoke_grant(
    payload: GameGrantRevoke, game_id: int = Path(gt=0),
    grant_id: int = Path(gt=0), user: AppUser = Depends(require_user),
) -> GameGrantResponse:
    try:
        record = revoke_game_grant(
            user_id=user.id, game_id=game_id,
            grant_id=grant_id, account_id=payload.account_id,
        )
    except (GrantNotFound, GrantForbidden, GrantConflict) as exc:
        raise _http_error(exc) from exc
    return GameGrantResponse(**record)


@router.get("/intel/games/{game_id}/grants/{grant_id}/preview")
def preview_grant(
    game_id: int = Path(gt=0),
    grant_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> dict[str, object]:
    """Owner-only preview. This never delegates a private read to the grantee."""
    try:
        return preview_game_grant(
            user_id=user.id, game_id=game_id, grant_id=grant_id,
            linked_account_id=linked_account_id,
        )
    except (GrantNotFound, GrantForbidden, GrantConflict) as exc:
        raise _http_error(exc) from exc


@router.get("/intel/games/{game_id}/received", response_model=None)
def received_scoped_game_intel(
    game_id: int = Path(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
    response: Response = None,
) -> dict[str, object]:
    """Only explicit, current-turn, allowlisted peer projections.

    This endpoint never delegates access to raw private turn payloads.
    """
    if response is not None:
        response.headers["Cache-Control"] = "no-store, private"
    try:
        return get_received_game_intel(
            user_id=user.id, game_id=game_id, linked_account_id=linked_account_id,
        )
    except (GrantNotFound, GrantForbidden, GrantConflict) as exc:
        raise _http_error(exc) from exc
