from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
import re
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HULL_NORMALIZATION_VERSION = "alpha-centroid-v3"
_HULL_VISIBLE_FRACTION = 0.58
_HULL_VISUAL_CENTER_Y = 0.42
_DOWNLOAD_TIMEOUT = httpx.Timeout(
    timeout=10.0,
    connect=4.0,
    read=8.0,
    write=5.0,
    pool=4.0,
)
_locks: dict[str, asyncio.Lock] = {}
_download_gate = asyncio.Semaphore(2)


class PrivateAssetError(RuntimeError):
    pass


def _cache_path(kind: str, name: str) -> Path:
    settings = get_settings()
    root = Path(settings.private_asset_cache_dir)
    return root / kind / f"{name}.png"


def _normalization_marker(path: Path) -> Path:
    return path.with_name(f"{path.name}.{_HULL_NORMALIZATION_VERSION}")


def _alpha_weighted_centroid(image: Image.Image) -> tuple[float, float]:
    alpha = image.getchannel("A")
    width, height = image.size
    weighted_x = 0.0
    weighted_y = 0.0
    total = 0.0

    # Squaring alpha suppresses barely-visible antialias/glow pixels so the
    # perceived body of the ship, rather than the raw transparent canvas,
    # defines the visual center.
    for y in range(height):
        for x in range(width):
            value = alpha.getpixel((x, y))
            if value <= 8:
                continue
            weight = float(value * value)
            weighted_x += x * weight
            weighted_y += y * weight
            total += weight

    if total <= 0:
        return (width / 2.0, height / 2.0)
    return (weighted_x / total, weighted_y / total)


def _normalized_hull_png(content: bytes) -> bytes:
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

            # The classic Nu artwork files often devote most of their canvas
            # to the ship itself. That makes a 22px Pixi sprite overflow a
            # 14px owner ring and makes the 58px DOM thumbnail look ~130% too
            # large. Normalize the visible hull to a stable fraction of the
            # transparent square instead of compensating in every renderer.
            side = max(width, height)
            canvas_side = max(
                side + 4,
                round(side / _HULL_VISIBLE_FRACTION),
            )
            canvas = Image.new(
                "RGBA",
                (canvas_side, canvas_side),
                (0, 0, 0, 0),
            )

            centroid_x, centroid_y = _alpha_weighted_centroid(artwork)
            desired_x = canvas_side / 2.0
            desired_y = canvas_side * _HULL_VISUAL_CENTER_Y

            offset_x = round(desired_x - centroid_x)
            offset_y = round(desired_y - centroid_y)
            offset_x = min(max(offset_x, 0), canvas_side - width)
            offset_y = min(max(offset_y, 0), canvas_side - height)

            canvas.alpha_composite(artwork, dest=(offset_x, offset_y))

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
        match = re.search(
            r"(?:^|/)(\d+)(?:\.png)?(?:$|[?#])",
            text,
            flags=re.IGNORECASE,
        )
        if match is None and text.isdigit():
            match_value = int(text)
            return match_value if match_value > 0 else None
        if match is not None:
            result = int(match.group(1))
            return result if result > 0 else None
    return None


def _normalized_hull_artwork_id(hull_id: int) -> int:
    if 1000 < hull_id < 4000:
        normalized = hull_id % 1000
        if normalized > 0:
            return normalized
    return hull_id


def _catalog_hull_image_id(hull_id: int) -> int | None:
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


async def _fetch_png_once(
    url: str,
    *,
    proxy_url: str | None,
) -> bytes | None:
    route = "direct" if proxy_url is None else "proxy"
    try:
        async with httpx.AsyncClient(
            timeout=_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            proxy=proxy_url,
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
            f"Planets.nu private asset {route} request failed: {url}"
        ) from exc

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PrivateAssetError(
            f"Planets.nu private asset {route} returned HTTP "
            f"{response.status_code}: {url}"
        ) from exc

    content = response.content
    if not content.startswith(_PNG_SIGNATURE):
        raise PrivateAssetError(
            f"Planets.nu private asset {route} response is not a PNG: {url}"
        )
    return content


async def _fetch_png(url: str) -> bytes | None:
    """Fetch public artwork without making the configured proxy a hard dependency.

    Static hull/planet PNGs carry no account credentials.  Try the direct CDN
    route first because the API proxy can be capacity-limited, then fall back to
    PLANETSNU_PROXY_URL when configured.  Limit total parallel source attempts
    so one missing hull cannot saturate the proxy with six simultaneous waits.
    """
    settings = get_settings()
    configured_proxy = settings.planetsnu_proxy_url or None
    routes: list[str | None] = [None]
    if configured_proxy is not None:
        routes.append(configured_proxy)

    errors: list[PrivateAssetError] = []
    async with _download_gate:
        for proxy_url in routes:
            try:
                return await _fetch_png_once(
                    url,
                    proxy_url=proxy_url,
                )
            except PrivateAssetError as exc:
                errors.append(exc)

    raise PrivateAssetError("; ".join(str(error) for error in errors))


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

    # The current Planets.nu client uses the 3D portrait artwork for the ship
    # survey/card whenever a 3D model exists. Classic artwork remains fallback.
    return [
        f"https://mobile.planets.nu/img/hulls3d/{image_id}_p.png",
        f"https://planets.nu/img/hulls3d/{image_id}_p.png",
        f"https://app.planets.nu/img/hulls3d/{image_id}_p.png",
        f"https://play.planets.nu/img/hulls3d/{image_id}_p.png",
        f"{configured}/{image_id}.png",
        f"https://mobile.planets.nu/img/hulls/{image_id}.png",
        f"https://planets.nu/img/hulls/{image_id}.png",
        f"https://app.planets.nu/img/hulls/{image_id}.png",
        f"https://play.planets.nu/img/hulls/{image_id}.png",
    ]


async def _try_hull_candidate(
    *,
    logical_image_id: int,
    source_image_id: int,
) -> tuple[Path | None, PrivateAssetError | None]:
    try:
        path = await _ensure_png_from_sources(
            kind="hulls",
            # Cache a successfully resolved alias under the logical hull id so
            # future requests do not repeatedly wait for a known-bad source.
            name=str(logical_image_id),
            urls=_hull_sources(source_image_id),
        )
        return path, None
    except PrivateAssetError as exc:
        return None, exc


async def ensure_hull_asset(
    hull_image_id: int,
    *,
    image_hint: int | None = None,
) -> Path | None:
    image_id = _normalized_hull_artwork_id(hull_image_id)
    cached = _cached_png("hulls", str(image_id))
    if cached is not None:
        return cached

    mapped_image_id = _catalog_hull_image_id(image_id)
    normalized_hint = (
        _normalized_hull_artwork_id(image_hint)
        if image_hint is not None and image_hint > 0
        else None
    )

    candidates: list[int] = []
    for candidate in (mapped_image_id, image_id, normalized_hint):
        if candidate is None or candidate <= 0 or candidate in candidates:
            continue
        candidates.append(candidate)

    errors: list[PrivateAssetError] = []
    saw_clean_miss = False
    for candidate in candidates:
        result, error = await _try_hull_candidate(
            logical_image_id=image_id,
            source_image_id=candidate,
        )
        if result is not None:
            return result
        if error is not None:
            errors.append(error)
        else:
            saw_clean_miss = True

    if errors and not saw_clean_miss and len(errors) == len(candidates):
        raise PrivateAssetError(
            "All candidate hull artwork sources failed: "
            + " | ".join(str(error) for error in errors)
        )
    return None


def _planet_sources(planet_image_name: str) -> list[str]:
    settings = get_settings()
    configured = settings.planetsnu_planet_asset_base_url.rstrip("/")
    return [
        f"{configured}/{planet_image_name}.png",
        f"https://mobile.planets.nu/img/planets/{planet_image_name}.png",
        f"https://planets.nu/img/planets/{planet_image_name}.png",
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
