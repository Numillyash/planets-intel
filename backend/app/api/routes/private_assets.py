import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.services.private_asset_cache import (
    PrivateAssetError,
    ensure_hull_asset,
    ensure_planet_asset,
)


router = APIRouter(prefix="/private-assets")
_PLANET_ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _file_response(path) -> FileResponse:
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get(
    "/hulls/{hull_image_id}.png",
    include_in_schema=False,
)
async def get_hull_asset(
    hull_image_id: int = Path(gt=0, le=10000),
    hint: int | None = Query(default=None, gt=0, le=10000),
    _user: AppUser = Depends(require_user),
) -> FileResponse:
    try:
        path = await ensure_hull_asset(
            hull_image_id,
            image_hint=hint,
        )
    except PrivateAssetError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hull image not available",
        )

    return _file_response(path)


@router.get(
    "/planets/{planet_image_name}.png",
    include_in_schema=False,
)
async def get_planet_asset(
    planet_image_name: str = Path(min_length=1, max_length=80),
    _user: AppUser = Depends(require_user),
) -> FileResponse:
    if _PLANET_ASSET_NAME_RE.fullmatch(planet_image_name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planet image not available",
        )

    try:
        path = await ensure_planet_asset(planet_image_name)
    except PrivateAssetError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planet image not available",
        )

    return _file_response(path)
