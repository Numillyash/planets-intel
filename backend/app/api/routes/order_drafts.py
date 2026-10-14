from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.order_draft import (
    PlanetOrderDraftResponse,
    PlanetOrderDraftUpsertRequest,
    ShipOrderDraftResponse,
    ShipOrderDraftUpsertRequest,
    StarbaseOrderDraftResponse,
    StarbaseOrderDraftUpsertRequest,
)
from app.services.entity_order_drafts import (
    discard_planet_order_draft,
    discard_starbase_order_draft,
    get_planet_order_draft,
    get_starbase_order_draft,
    upsert_planet_order_draft,
    upsert_starbase_order_draft,
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


def _missing(entity: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No local order draft exists for this {entity}",
    )


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
        _missing("ship")
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
            movement_mode=payload.movement_mode,
            intercept_target_ship_id=payload.intercept_target_ship_id,
            tow_target_ship_id=payload.tow_target_ship_id,
            friendly_code=payload.friendly_code,
            mission=payload.mission,
            primary_enemy_id=payload.primary_enemy_id,
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


@router.get(
    "/games/{game_id}/order-drafts/planets/{planet_id}",
    response_model=PlanetOrderDraftResponse,
)
def planet_order_draft(
    game_id: int = Path(gt=0),
    planet_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> PlanetOrderDraftResponse:
    try:
        result = get_planet_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            planet_id=planet_id,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    if result is None:
        _missing("planet")
    return PlanetOrderDraftResponse(**result)


@router.put(
    "/games/{game_id}/order-drafts/planets/{planet_id}",
    response_model=PlanetOrderDraftResponse,
)
def save_planet_order_draft(
    payload: PlanetOrderDraftUpsertRequest,
    game_id: int = Path(gt=0),
    planet_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> PlanetOrderDraftResponse:
    try:
        result = upsert_planet_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            planet_id=planet_id,
            friendly_code=payload.friendly_code,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    return PlanetOrderDraftResponse(**result)


@router.delete(
    "/games/{game_id}/order-drafts/planets/{planet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_planet_order_draft(
    game_id: int = Path(gt=0),
    planet_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> Response:
    discard_planet_order_draft(
        user_id=user.id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        turn=turn,
        planet_id=planet_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/games/{game_id}/order-drafts/starbases/{starbase_id}",
    response_model=StarbaseOrderDraftResponse,
)
def starbase_order_draft(
    game_id: int = Path(gt=0),
    starbase_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> StarbaseOrderDraftResponse:
    try:
        result = get_starbase_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            starbase_id=starbase_id,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    if result is None:
        _missing("starbase")
    return StarbaseOrderDraftResponse(**result)


@router.put(
    "/games/{game_id}/order-drafts/starbases/{starbase_id}",
    response_model=StarbaseOrderDraftResponse,
)
def save_starbase_order_draft(
    payload: StarbaseOrderDraftUpsertRequest,
    game_id: int = Path(gt=0),
    starbase_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> StarbaseOrderDraftResponse:
    try:
        result = upsert_starbase_order_draft(
            user_id=user.id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            starbase_id=starbase_id,
            primary_order=payload.primary_order,
        )
    except (OrderDraftAccessError, OrderDraftNotFound) as exc:
        _raise_service_error(exc)
        raise AssertionError("unreachable")
    return StarbaseOrderDraftResponse(**result)


@router.delete(
    "/games/{game_id}/order-drafts/starbases/{starbase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_starbase_order_draft(
    game_id: int = Path(gt=0),
    starbase_id: int = Path(gt=0),
    turn: int = Query(gt=0),
    linked_account_id: int = Query(gt=0),
    user: AppUser = Depends(require_user),
) -> Response:
    discard_starbase_order_draft(
        user_id=user.id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        turn=turn,
        starbase_id=starbase_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
