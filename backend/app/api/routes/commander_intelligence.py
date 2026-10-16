from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.schemas.commander_intelligence import CommanderIntelligenceResponse
from app.services.commander_intelligence import get_commander_intelligence


router = APIRouter(
    prefix="/games",
)


@router.get(
    "/{game_id}/commander-intelligence",
    response_model=CommanderIntelligenceResponse,
)
async def commander_intelligence(
    game_id: int = Path(gt=0),
    _user: AppUser = Depends(require_user),
) -> CommanderIntelligenceResponse:
    result = await get_commander_intelligence(game_id=game_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game is not present in the canonical IntelBoard cache",
        )
    return CommanderIntelligenceResponse(**result)


@router.get(
    "/{game_id}/public-commander-intelligence",
    response_model=CommanderIntelligenceResponse,
)
async def public_commander_intelligence(
    game_id: int = Path(gt=0),
    _user: AppUser = Depends(require_user),
) -> CommanderIntelligenceResponse:
    """Observer-independent public source, never private loadturn or grants."""
    result = await get_commander_intelligence(game_id=game_id, public_roster=True)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public sector not found or source roster unavailable",
        )
    return CommanderIntelligenceResponse(**result)
