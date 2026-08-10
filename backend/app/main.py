from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()

FRONTEND_DIR = Path("/app/frontend_dist")
INDEX_FILE = FRONTEND_DIR / "index.html"
ASSETS_DIR = FRONTEND_DIR / "assets"


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
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
