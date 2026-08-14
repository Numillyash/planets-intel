from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.order_draft import (
    ShipOrderDraftResponse,
    ShipOrderDraftUpsertRequest,
)
from app.services.order_drafts import (
    OrderDraftAccessError,
    OrderDraftNotFound,
    discard_ship_order_draft,
    get_ship_order_draft,
    upsert_ship_order_draft,
)


router = APIRouter()


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, OrderDraftAccessError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if isinstance(exc, OrderDraftNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    raise exc


@router.get(
    "/games/{game_id}/order-drafts/ships/{ship_id}",
    response_model=ShipOrderDraftResponse,
)
def ship_order_draft(
    game_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> ShipOrderDraftResponse:
    try:
        result = get_ship_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            ship_id=ship_id,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No local order draft exists for this ship",
        )
    return ShipOrderDraftResponse(**result)


@router.put(
    "/games/{game_id}/order-drafts/ships/{ship_id}",
    response_model=ShipOrderDraftResponse,
)
def save_ship_order_draft(
    payload: ShipOrderDraftUpsertRequest,
    game_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> ShipOrderDraftResponse:
    try:
        result = upsert_ship_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            ship_id=ship_id,
            warp=payload.warp,
            waypoint_x=payload.waypoint_x,
            waypoint_y=payload.waypoint_y,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    return ShipOrderDraftResponse(**result)


@router.delete(
    "/games/{game_id}/order-drafts/ships/{ship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ship_order_draft(
    game_id: int = Path(gt=0),
    ship_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> Response:
    try:
        discard_ship_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            ship_id=ship_id,
        )
    except OrderDraftAccessError as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
