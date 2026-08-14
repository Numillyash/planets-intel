from fastapi import APIRouter

from app.api.routes.account_games import router as account_games_router
from app.api.routes.auth import router as auth_router
from app.api.routes.combat_replay import router as combat_replay_router
from app.api.routes.games import router as games_router
from app.api.routes.health import router as health_router
from app.api.routes.historical_intel import router as historical_intel_router
from app.api.routes.intel_sharing import router as intel_sharing_router
from app.api.routes.private_intel import router as private_intel_router
from app.api.routes.planets_accounts import (
    router as planets_accounts_router,
)
from app.api.routes.scores import router as scores_router


api_router = APIRouter()

api_router.include_router(
    health_router,
    tags=["health"],
)

api_router.include_router(
    auth_router,
    tags=["auth"],
)

api_router.include_router(
    account_games_router,
    tags=["account-games"],
)

api_router.include_router(
    planets_accounts_router,
    tags=["planets-accounts"],
)

api_router.include_router(
    intel_sharing_router,
    tags=["intel-sharing"],
)

api_router.include_router(
    games_router,
    tags=["games"],
)

api_router.include_router(
    private_intel_router,
    tags=["private-intel"],
)

api_router.include_router(
    historical_intel_router,
    tags=["historical-intel"],
)

api_router.include_router(
    combat_replay_router,
    tags=["combat-replay"],
)

api_router.include_router(
    scores_router,
    tags=["scores"],
)
