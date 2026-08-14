from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.services.private_asset_cache import PrivateAssetError, ensure_hull_asset


router = APIRouter(prefix="/private-assets")


@router.get(
    "/hulls/{hull_id}.png",
    include_in_schema=False,
)
async def get_hull_asset(
    hull_id: int = Path(gt=0, le=10000),
    _user: AppUser = Depends(require_user),
) -> FileResponse:
    try:
        path = await ensure_hull_asset(hull_id)
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

    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=604800, immutable",
        },
    )
