from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies.auth import require_user
from app.models.user import AppUser
from app.planetsnu.client import PlanetsNuError
from app.schemas.private_intel import (
    PlanetObservationResponse,
    ShipObservationResponse,
    StarbaseObservationResponse,
    StellarCartographyObservationResponse,
)
from app.services.public_archive_turn import (
    ArchiveNotPublicOrFinished,
    ArchiveSourceMismatch,
    fetch_finished_public_turn,
)
from pydantic import BaseModel, Field
from typing import Literal


router = APIRouter(prefix="/games")


class PublicArchiveCounts(BaseModel):
    planets: int
    ships: int
    starbases: int


class PublicArchiveTurnResponse(BaseModel):
    mode: Literal["public_finished_archive"]
    source: str
    game_id: int
    turn: int
    player_slot_id: int
    counts: PublicArchiveCounts
    planets: list[PlanetObservationResponse]
    ships: list[ShipObservationResponse]
    starbases: list[StarbaseObservationResponse]
    stellar_cartography: list[StellarCartographyObservationResponse] = Field(default_factory=list)


@router.get(
    "/{game_id}/public-archive/turn",
    response_model=PublicArchiveTurnResponse,
)
async def public_archive_turn(
    game_id: int = Path(gt=0),
    player_id: int = Query(gt=0, le=35),
    turn: int = Query(gt=0),
    _user: AppUser = Depends(require_user),
) -> PublicArchiveTurnResponse:
    """Read only: no API key, no observer DB access or private snapshot writes."""
    try:
        data = await fetch_finished_public_turn(game_id, player_id, turn)
    except ArchiveNotPublicOrFinished as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ArchiveSourceMismatch as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except PlanetsNuError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Planets.nu historical turn unavailable",
        ) from exc
    return PublicArchiveTurnResponse(**data)
