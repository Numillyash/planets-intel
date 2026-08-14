from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.core.config import get_settings


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_DOWNLOAD_ATTEMPTS = 3
_locks: dict[int, asyncio.Lock] = {}


class PrivateAssetError(RuntimeError):
    pass


def _cache_path(hull_id: int) -> Path:
    settings = get_settings()
    root = Path(settings.private_asset_cache_dir)
    return root / "hulls" / f"{hull_id}.png"


def cached_hull_path(hull_id: int) -> Path | None:
    path = _cache_path(hull_id)
    if not path.is_file() or path.stat().st_size < len(_PNG_SIGNATURE):
        return None
    try:
        with path.open("rb") as handle:
            if handle.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
                return None
    except OSError:
        return None
    return path


async def _download_hull_asset(url: str) -> httpx.Response:
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
        f"Planets.nu hull asset download failed after {_MAX_DOWNLOAD_ATTEMPTS} attempts"
    ) from last_error


async def ensure_hull_asset(hull_id: int) -> Path | None:
    cached = cached_hull_path(hull_id)
    if cached is not None:
        return cached

    lock = _locks.setdefault(hull_id, asyncio.Lock())
    async with lock:
        cached = cached_hull_path(hull_id)
        if cached is not None:
            return cached

        settings = get_settings()
        base_url = settings.planetsnu_hull_asset_base_url.rstrip("/")
        url = f"{base_url}/{hull_id}.png"
        response = await _download_hull_asset(url)

        if response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PrivateAssetError(
                f"Planets.nu hull asset returned HTTP {response.status_code}"
            ) from exc

        content = response.content
        if not content.startswith(_PNG_SIGNATURE):
            raise PrivateAssetError(
                "Planets.nu hull asset response is not a PNG"
            )

        target = _cache_path(hull_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".png.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return target
