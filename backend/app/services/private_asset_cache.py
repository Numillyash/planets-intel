from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog


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


def _positive_image_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(".png"):
            text = text[:-4]
        if text.isdigit():
            result = int(text)
            return result if result > 0 else None
    return None


def _normalized_hull_artwork_id(hull_id: int) -> int:
    # The Nu client namespaces many campaign/upgraded hull ids in the 1000,
    # 2000 and 3000 ranges while reusing the base hull artwork. Historic Nu
    # addons mirror the client by stripping that namespace for hull images.
    if 1000 < hull_id < 4000:
        normalized = hull_id % 1000
        if normalized > 0:
            return normalized
    return hull_id


def _catalog_hull_image_id(hull_id: int) -> int | None:
    """Resolve an explicit Nu artwork id when it differs from the hull id."""
    with SessionLocal() as session:
        catalogs = session.execute(
            select(GameRuleCatalog)
            .order_by(GameRuleCatalog.observed_turn.desc())
        ).scalars().all()

        for catalog in catalogs:
            for hull in catalog.hulls:
                raw_id = _positive_image_id(hull.get("id"))
                if raw_id is None:
                    continue
                if raw_id != hull_id and _normalized_hull_artwork_id(raw_id) != hull_id:
                    continue
                for key in ("img", "imageid", "image_id", "image"):
                    image_id = _positive_image_id(hull.get(key))
                    if image_id is not None:
                        return _normalized_hull_artwork_id(image_id)
                return None
    return None


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


async def _ensure_png_from_sources(
    *,
    kind: str,
    name: str,
    urls: list[str],
) -> Path | None:
    cached = _cached_png(kind, name)
    if cached is not None:
        return cached

    last_error: PrivateAssetError | None = None
    for url in urls:
        try:
            result = await _ensure_png(kind=kind, name=name, url=url)
        except PrivateAssetError as exc:
            last_error = exc
            continue
        if result is not None:
            return result

    if last_error is not None:
        raise last_error
    return None


def cached_hull_path(hull_image_id: int) -> Path | None:
    image_id = _normalized_hull_artwork_id(hull_image_id)
    return _cached_png("hulls", str(image_id))


async def ensure_hull_asset(hull_image_id: int) -> Path | None:
    settings = get_settings()
    image_id = _normalized_hull_artwork_id(hull_image_id)
    base_url = settings.planetsnu_hull_asset_base_url.rstrip("/")

    direct = await _ensure_png_from_sources(
        kind="hulls",
        name=str(image_id),
        urls=[
            f"{base_url}/{image_id}.png",
            f"https://play.planets.nu/img/hulls/{image_id}.png",
        ],
    )
    if direct is not None:
        return direct

    mapped_image_id = _catalog_hull_image_id(image_id)
    if mapped_image_id is None or mapped_image_id == image_id:
        return None

    return await _ensure_png_from_sources(
        kind="hulls",
        name=str(image_id),
        urls=[
            f"{base_url}/{mapped_image_id}.png",
            f"https://play.planets.nu/img/hulls/{mapped_image_id}.png",
        ],
    )


async def ensure_planet_asset(planet_image_name: str) -> Path | None:
    settings = get_settings()
    base_url = settings.planetsnu_planet_asset_base_url.rstrip("/")
    return await _ensure_png_from_sources(
        kind="planets",
        name=planet_image_name,
        urls=[
            f"{base_url}/{planet_image_name}.png",
            f"https://play.planets.nu/img/planets/{planet_image_name}.png",
        ],
    )


async def ensure_unknown_planet_asset() -> Path | None:
    return await ensure_planet_asset("unknown")
