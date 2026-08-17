import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.services.background_private_refresh import (
    background_private_refresh_loop,
    cancel_background_task,
)


settings = get_settings()

FRONTEND_DIR = Path("/app/frontend_dist")
INDEX_FILE = FRONTEND_DIR / "index.html"
ASSETS_DIR = FRONTEND_DIR / "assets"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Private observations are collection infrastructure, not a browser-side
    # convenience. Keep all running linked games fresh even while the user is
    # on the game picker or has no dashboard tab open.
    refresh_task = asyncio.create_task(
        background_private_refresh_loop(),
        name="private-intel-background-refresh",
    )
    try:
        yield
    finally:
        await cancel_background_task(refresh_task)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# API routes must be registered before SPA fallback.
app.include_router(
    api_router,
    prefix="/api",
)


if ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=ASSETS_DIR),
        name="frontend-assets",
    )


@app.api_route(
    "/",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
async def frontend_index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.api_route(
    "/{path:path}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
async def frontend_spa(path: str) -> FileResponse:
    """
    SPA fallback.

    React Router routes will eventually resolve here.
    API routes are registered above and therefore are not handled by
    this fallback.
    """
    return FileResponse(INDEX_FILE)
