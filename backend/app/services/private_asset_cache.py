from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.core.config import get_settings


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_DOWNLOAD_ATTEMPTS = 3
_locks: dict[str, asyncio.Lock] = {}


class PrivateAssetError(RuntimeError):
    pass


def _cache_path(kind: str, name: str) -> Path:
    settings = get_settings()
    root = Path(settings.private_asset_cache_dir)
    return root / kind / f"{name}.png"


def _cached_png(kind: str, name: str) -> Path | None:
    path = _cache_path(kind, name)
    if not path.is_file() or path.stat().st_size < len(_PNG_SIGNATURE):
        return None
    try:
        with path.open("rb") as handle:
            if handle.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
                return None
    except OSError:
        return None
    return path


async def _download_png(url: str) -> httpx.Response:
    last_error: httpx.HTTPError | None = None

    for attempt in range(1, _MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=10.0),
                follow_redirects=True,
                trust_env=False,
            ) as client:
                return await client.get(
                    url,
                    headers={
                        "Referer": "https://planets.nu/",
                        "User-Agent": "Mozilla/5.0",
                    },
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt < _MAX_DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(0.35 * attempt)

    raise PrivateAssetError(
        "Planets.nu private asset download failed after "
        f"{_MAX_DOWNLOAD_ATTEMPTS} attempts"
    ) from last_error


async def _ensure_png(
    *,
    kind: str,
    name: str,
    url: str,
) -> Path | None:
    cached = _cached_png(kind, name)
    if cached is not None:
        return cached

    lock_key = f"{kind}/{name}"
    lock = _locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        cached = _cached_png(kind, name)
        if cached is not None:
            return cached

        response = await _download_png(url)
        if response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PrivateAssetError(
                f"Planets.nu private asset returned HTTP {response.status_code}"
            ) from exc

        content = response.content
        if not content.startswith(_PNG_SIGNATURE):
            raise PrivateAssetError(
                "Planets.nu private asset response is not a PNG"
            )

        target = _cache_path(kind, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".png.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return target


def cached_hull_path(hull_image_id: int) -> Path | None:
    return _cached_png("hulls", str(hull_image_id))


async def ensure_hull_asset(hull_image_id: int) -> Path | None:
    settings = get_settings()
    base_url = settings.planetsnu_hull_asset_base_url.rstrip("/")
    return await _ensure_png(
        kind="hulls",
        name=str(hull_image_id),
        url=f"{base_url}/{hull_image_id}.png",
    )


async def ensure_unknown_planet_asset() -> Path | None:
    settings = get_settings()
    base_url = settings.planetsnu_planet_asset_base_url.rstrip("/")
    return await _ensure_png(
        kind="planets",
        name="unknown",
        url=f"{base_url}/unknown.png",
    )
