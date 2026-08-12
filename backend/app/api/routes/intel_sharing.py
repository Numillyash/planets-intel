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
from app.schemas.intel_sharing import (
    DashboardIntelShareDecision,
    DashboardIntelShareRequest,
    DashboardIntelShareResponse,
    DashboardIntelShareRevokeResponse,
    DashboardIntelSharesResponse,
)
from app.services.intel_sharing import (
    IntelShareAccountNotFound,
    IntelShareError,
    IntelShareForbidden,
    IntelShareTargetAmbiguous,
    IntelShareTargetNotFound,
    accept_dashboard_intel_share,
    list_dashboard_intel_shares,
    request_dashboard_intel_share,
    revoke_dashboard_intel_share,
)


router = APIRouter()


def _share_http_error(exc: IntelShareError) -> HTTPException:
    if isinstance(exc, IntelShareForbidden):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    if isinstance(
        exc,
        (IntelShareAccountNotFound, IntelShareTargetNotFound),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(exc, IntelShareTargetAmbiguous):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/intel/shares",
    response_model=DashboardIntelSharesResponse,
)
def get_dashboard_intel_shares(
    user: AppUser = Depends(require_user),
) -> DashboardIntelSharesResponse:
    return DashboardIntelSharesResponse(
        shares=list_dashboard_intel_shares(
            user_id=user.id,
        )
    )


@router.post(
    "/intel/shares",
    response_model=DashboardIntelShareResponse,
)
def create_dashboard_intel_share(
    payload: DashboardIntelShareRequest,
    user: AppUser = Depends(require_user),
) -> DashboardIntelShareResponse:
    try:
        result = request_dashboard_intel_share(
            user_id=user.id,
            source_account_id=payload.source_account_id,
            target_planets_username=payload.target_planets_username,
        )
    except IntelShareError as exc:
        raise _share_http_error(exc) from exc

    return DashboardIntelShareResponse(**result)


@router.post(
    "/intel/shares/{share_id}/accept",
    response_model=DashboardIntelShareResponse,
)
def accept_dashboard_share(
    payload: DashboardIntelShareDecision,
    share_id: int = Path(gt=0),
    user: AppUser = Depends(require_user),
) -> DashboardIntelShareResponse:
    try:
        result = accept_dashboard_intel_share(
            user_id=user.id,
            share_id=share_id,
            account_id=payload.account_id,
        )
    except IntelShareError as exc:
        raise _share_http_error(exc) from exc

    return DashboardIntelShareResponse(**result)


@router.delete(
    "/intel/shares/{share_id}",
    response_model=DashboardIntelShareRevokeResponse,
)
def delete_dashboard_share(
    share_id: int = Path(gt=0),
    account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> DashboardIntelShareRevokeResponse:
    removed = revoke_dashboard_intel_share(
        user_id=user.id,
        share_id=share_id,
        account_id=account_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard intel share not found",
        )

    return DashboardIntelShareRevokeResponse(
        success=True
    )
