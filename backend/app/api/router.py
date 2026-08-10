from fastapi import APIRouter

from app.api.routes.games import router as games_router
from app.api.routes.health import router as health_router
from app.api.routes.scores import router as scores_router


api_router = APIRouter()

api_router.include_router(
    health_router,
    tags=["health"],
)

api_router.include_router(
    games_router,
    tags=["games"],
)

api_router.include_router(
    scores_router,
    tags=["scores"],
)
