from fastapi import APIRouter

from app.services.background_private_refresh import private_refresh_health_snapshot

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "planets-intel-backend",
    }


@router.get("/health/private-refresh")
async def private_refresh_health() -> dict[str, object]:
    return private_refresh_health_snapshot()
