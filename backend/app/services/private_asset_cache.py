from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HULL_NORMALIZATION_VERSION = "alpha-center-v1"
_DOWNLOAD_TIMEOUT = httpx.Timeout(
    timeout=7.0,
    connect=4.0,
    read=5.0,
    write=5.0,
    pool=4.0,
)
_locks: dict[str, asyncio.Lock] = {}


class PrivateAssetError(RuntimeError):
    pass


def _cache_path(kind: str, name: str) -> Path:
    settings = get_settings()
    root = Path(settings.private_asset_cache_dir)
    return root / kind / f"{name}.png"


def _normalization_marker(path: Path) -> Path:
    return path.with_name(f"{path.name}.{_HULL_NORMALIZATION_VERSION}")


def _normalized_hull_png(content: bytes) -> bytes:
    """Center the visible alpha bounds without distorting the Nu artwork."""
    try:
        with Image.open(BytesIO(content)) as source:
            rgba = source.convert("RGBA")
            alpha_bounds = rgba.getchannel("A").getbbox()
            if alpha_bounds is None:
                return content

            artwork = rgba.crop(alpha_bounds)
            width, height = artwork.size
            if width <= 0 or height <= 0:
                return content

            side = max(width, height)
            padding = max(2, round(side * 0.08))
            canvas_side = side + padding * 2
            canvas = Image.new(
                "RGBA",
                (canvas_side, canvas_side),
                (0, 0, 0, 0),
            )
            offset = (
                (canvas_side - width) // 2,
                (canvas_side - height) // 2,
            )
            canvas.alpha_composite(artwork, dest=offset)

            output = BytesIO()
            canvas.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (OSError, UnidentifiedImageError, ValueError):
        return content


def _normalize_cached_hull(path: Path) -> None:
    marker = _normalization_marker(path)
    if marker.is_file():
        return

    try:
        content = path.read_bytes()
        normalized = _normalized_hull_png(content)
        if normalized.startswith(_PNG_SIGNATURE):
            temporary = path.with_suffix(".png.normalize.tmp")
            temporary.write_bytes(normalized)
            temporary.replace(path)
            marker.touch()
    except OSError:
        return


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

    if kind == "hulls":
        _normalize_cached_hull(path)
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
                if (
                    raw_id != hull_id
                    and _normalized_hull_artwork_id(raw_id) != hull_id
                ):
                    continue
                for key in ("img", "imageid", "image_id", "image"):
                    image_id = _positive_image_id(hull.get(key))
                    if image_id is not None:
                        return _normalized_hull_artwork_id(image_id)
                return None
    return None


async def _fetch_png(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            timeout=_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "Referer": "https://planets.nu/",
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/png,image/*;q=0.8,*/*;q=0.1",
                },
            )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise PrivateAssetError(
            f"Planets.nu private asset source timed out: {url}"
        ) from exc

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PrivateAssetError(
            f"Planets.nu private asset returned HTTP "
            f"{response.status_code}: {url}"
        ) from exc

    content = response.content
    if not content.startswith(_PNG_SIGNATURE):
        raise PrivateAssetError(
            f"Planets.nu private asset response is not a PNG: {url}"
        )
    return content


def _unique_urls(urls: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


async def _ensure_png_from_sources(
    *,
    kind: str,
    name: str,
    urls: list[str],
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

        source_urls = _unique_urls(urls)
        tasks = [asyncio.create_task(_fetch_png(url)) for url in source_urls]
        errors: list[PrivateAssetError] = []
        content: bytes | None = None

        try:
            for completed in asyncio.as_completed(tasks):
                try:
                    candidate = await completed
                except PrivateAssetError as exc:
                    errors.append(exc)
                    continue
                if candidate is None:
                    continue
                content = candidate
                break
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if content is None:
            if errors and len(errors) == len(tasks):
                raise PrivateAssetError(
                    "All Planets.nu private asset sources failed: "
                    + "; ".join(str(error) for error in errors)
                )
            return None

        if kind == "hulls":
            content = _normalized_hull_png(content)

        target = _cache_path(kind, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".png.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        if kind == "hulls":
            _normalization_marker(target).touch()
        return target


def cached_hull_path(hull_image_id: int) -> Path | None:
    image_id = _normalized_hull_artwork_id(hull_image_id)
    return _cached_png("hulls", str(image_id))


def _hull_sources(image_id: int) -> list[str]:
    settings = get_settings()
    configured = settings.planetsnu_hull_asset_base_url.rstrip("/")
    return [
        f"{configured}/{image_id}.png",
        f"https://mobile.planets.nu/img/hulls/{image_id}.png",
        f"https://app.planets.nu/img/hulls/{image_id}.png",
        f"https://play.planets.nu/img/hulls/{image_id}.png",
    ]


async def ensure_hull_asset(hull_image_id: int) -> Path | None:
    image_id = _normalized_hull_artwork_id(hull_image_id)

    direct = await _ensure_png_from_sources(
        kind="hulls",
        name=str(image_id),
        urls=_hull_sources(image_id),
    )
    if direct is not None:
        return direct

    mapped_image_id = _catalog_hull_image_id(image_id)
    if mapped_image_id is None or mapped_image_id == image_id:
        return None

    return await _ensure_png_from_sources(
        kind="hulls",
        name=str(image_id),
        urls=_hull_sources(mapped_image_id),
    )


def _planet_sources(planet_image_name: str) -> list[str]:
    settings = get_settings()
    configured = settings.planetsnu_planet_asset_base_url.rstrip("/")
    return [
        f"{configured}/{planet_image_name}.png",
        f"https://mobile.planets.nu/img/planets/{planet_image_name}.png",
        f"https://app.planets.nu/img/planets/{planet_image_name}.png",
        f"https://play.planets.nu/img/planets/{planet_image_name}.png",
    ]


async def ensure_planet_asset(planet_image_name: str) -> Path | None:
    return await _ensure_png_from_sources(
        kind="planets",
        name=planet_image_name,
        urls=_planet_sources(planet_image_name),
    )


async def ensure_unknown_planet_asset() -> Path | None:
    return await ensure_planet_asset("unknown")
