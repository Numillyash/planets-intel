from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient
from app.services.private_refresh import (
    accessible_refresh_account_ids,
    refresh_accessible_private_intel,
)


# Uvicorn installs handlers for its own logger hierarchy, while arbitrary
# module loggers can stay below the configured output level. Background
# collection is operational infrastructure, so route its INFO diagnostics
# through uvicorn.error to make successful scheduler passes observable in
# container logs without promoting them to warnings.
LOGGER = logging.getLogger("uvicorn.error")

BACKGROUND_REFRESH_INTERVAL_SECONDS = 5 * 60
BACKGROUND_REFRESH_DEGRADED_RETRY_SECONDS = 60
BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS = 15
BACKGROUND_REFRESH_TRANSPORT_PROBE_TIMEOUT_SECONDS = 12.0
MAX_CONCURRENT_GAME_REFRESHES = 2

_PRIVATE_REFRESH_HEALTH: dict[str, Any] = {
    "scheduler_running": False,
    "transport_status": "unknown",
    "transport_route": None,
    "proxy_configured": None,
    "last_transport_check_at": None,
    "last_transport_error": None,
    "consecutive_transport_failures": 0,
    "last_iteration_started_at": None,
    "last_iteration_completed_at": None,
    "last_iteration_status": "never",
    "last_success_at": None,
    "last_summary": None,
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def private_refresh_health_snapshot() -> dict[str, Any]:
    """Return non-secret in-memory scheduler health for operations/diagnostics."""

    snapshot = dict(_PRIVATE_REFRESH_HEALTH)
    summary = snapshot.get("last_summary")
    if isinstance(summary, dict):
        snapshot["last_summary"] = dict(summary)
    return snapshot


async def probe_background_private_transport() -> tuple[bool, dict[str, Any]]:
    """Check the exact transport path private collection intends to use."""

    checked_at = _utc_iso()
    client = PlanetsNuClient()

    try:
        result = await client.probe_private_transport(
            timeout_seconds=BACKGROUND_REFRESH_TRANSPORT_PROBE_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        failures = int(_PRIVATE_REFRESH_HEALTH["consecutive_transport_failures"]) + 1
        diagnostic = {
            "ok": False,
            "error_type": type(exc).__name__,
            "detail": str(exc),
        }
        _PRIVATE_REFRESH_HEALTH.update(
            {
                "transport_status": "failed",
                "transport_route": "proxy" if client.proxy_url else "direct",
                "proxy_configured": client.proxy_url is not None,
                "last_transport_check_at": checked_at,
                "last_transport_error": f"{type(exc).__name__}: {exc}",
                "consecutive_transport_failures": failures,
            }
        )
        return False, diagnostic

    _PRIVATE_REFRESH_HEALTH.update(
        {
            "transport_status": "ok",
            "transport_route": result.get("route"),
            "proxy_configured": bool(result.get("proxy_configured")),
            "last_transport_check_at": checked_at,
            "last_transport_error": None,
            "consecutive_transport_failures": 0,
        }
    )
    return True, result


def _membership_join_condition():
    """Return the conservative linked-account -> canonical-slot identity match.

    A linked account can temporarily have no verified external Planets account
    id. Comparing that NULL directly with ``GamePlayerSlot.account_id`` would
    compile to ``IS NULL`` and could accidentally match unrelated anonymous or
    sentinel-shaped slots in many games. Only a positive verified account id is
    allowed into the id branch; canonical username remains the explicit
    fallback used for dead/sentinel identity cases.
    """

    return or_(
        and_(
            PlanetsAccount.planets_account_id.is_not(None),
            PlanetsAccount.planets_account_id > 0,
            GamePlayerSlot.account_id == PlanetsAccount.planets_account_id,
        ),
        and_(
            func.length(func.trim(PlanetsAccount.planets_username)) > 0,
            func.lower(GamePlayerSlot.username)
            == func.lower(PlanetsAccount.planets_username),
        ),
    )


def running_private_refresh_targets() -> list[tuple[int, int]]:
    """Return canonical ``(local_user_id, game_id)`` refresh targets.

    This path covers games already known to the local canonical database. Live
    discovery below complements it so a newly joined/started Planets.nu game can
    enter collection before a manual dashboard open has seeded GamePlayerSlot.
    """

    with SessionLocal() as session:
        rows = session.execute(
            select(
                PlanetsAccount.user_id,
                GamePlayerSlot.game_id,
            )
            .join(
                GamePlayerSlot,
                _membership_join_condition(),
            )
            .join(Game, Game.id == GamePlayerSlot.game_id)
            .where(
                PlanetsAccount.is_active.is_(True),
                or_(
                    Game.status_id == 2,
                    Game.status_name.ilike("running"),
                    Game.status_name.ilike("joining"),
                ),
            )
        ).all()

    return sorted({(int(user_id), int(game_id)) for user_id, game_id in rows})


def _active_live_discovery_accounts() -> list[tuple[int, str]]:
    """Return active local linked-account usernames for lightweight game discovery."""

    with SessionLocal() as session:
        rows = session.execute(
            select(
                PlanetsAccount.user_id,
                PlanetsAccount.planets_username,
            ).where(PlanetsAccount.is_active.is_(True))
        ).all()

    unique: dict[tuple[int, str], tuple[int, str]] = {}
    for user_id, raw_username in rows:
        username = str(raw_username or "").strip()
        if not username:
            continue
        key = (int(user_id), username.casefold())
        unique.setdefault(key, (int(user_id), username))

    return sorted(
        unique.values(),
        key=lambda item: (item[0], item[1].casefold()),
    )


def _remote_game_is_refresh_candidate(raw: dict[str, Any]) -> bool:
    """Accept only valid Running/Joining games returned by ``games/list``."""

    raw_game_id = raw.get("id")
    if isinstance(raw_game_id, bool):
        return False
    try:
        game_id = int(raw_game_id)
    except (TypeError, ValueError):
        return False
    if game_id <= 0:
        return False

    raw_status = raw.get("status")
    status_id: int | None = None
    if not isinstance(raw_status, bool):
        try:
            status_id = int(raw_status)
        except (TypeError, ValueError):
            status_id = None

    status_name = raw.get("statusname")
    normalized_status_name = (
        status_name.strip().casefold()
        if isinstance(status_name, str)
        else ""
    )
    return status_id == 2 or normalized_status_name in {"running", "joining"}


async def discover_live_private_refresh_targets() -> dict[str, Any]:
    """Discover active games even when they are not canonical locally yet.

    The game chooser already uses the public ``games/list`` endpoint, so a new
    game can be visible to the user before a canonical Game/GamePlayerSlot row
    exists. Background collection must use the same discovery source or the new
    game would never become a scheduler target without a manual refresh/open.

    Discovery itself is read-only. ``refresh_accessible_private_intel`` performs
    the existing public sync first, which seeds the canonical game/roster, and
    then refreshes private loadturn observations through the normal path.
    """

    accounts = _active_live_discovery_accounts()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_GAME_REFRESHES)
    targets: set[tuple[int, int]] = set()
    failures = 0
    remote_games_seen = 0
    candidate_games_seen = 0

    async def discover_one(user_id: int, username: str) -> None:
        nonlocal failures, remote_games_seen, candidate_games_seen
        async with semaphore:
            try:
                games = await PlanetsNuClient().games_for_username(username)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # one account must not stop the scheduler
                failures += 1
                LOGGER.warning(
                    "background game discovery failed user=%s username=%r: %s",
                    user_id,
                    username,
                    exc,
                    exc_info=True,
                )
                return

            remote_games_seen += len(games)
            for raw in games:
                if not _remote_game_is_refresh_candidate(raw):
                    continue
                candidate_games_seen += 1
                targets.add((user_id, int(raw["id"])))

    await asyncio.gather(
        *(discover_one(user_id, username) for user_id, username in accounts)
    )

    return {
        "accounts": len(accounts),
        "failures": failures,
        "remote_games_seen": remote_games_seen,
        "candidate_games_seen": candidate_games_seen,
        "targets": sorted(targets),
    }


def deduplicate_private_refresh_targets(
    targets: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Collapse equivalent local-user jobs without collapsing different shares.

    Two local users can mutually share the same observers. A target is
    equivalent only when both the game id and exact accessible linked-account id
    set match. Different share topologies therefore remain separate jobs.
    """

    unique: list[tuple[int, int]] = []
    seen: set[tuple[int, tuple[int, ...]]] = set()

    for user_id, game_id in targets:
        signature = (game_id, accessible_refresh_account_ids(user_id))
        if signature in seen:
            continue
        seen.add(signature)
        unique.append((user_id, game_id))

    return unique


async def refresh_all_running_private_intel_once() -> dict[str, Any]:
    canonical_targets = running_private_refresh_targets()
    discovery = await discover_live_private_refresh_targets()
    discovered_targets = list(discovery["targets"])
    raw_targets = sorted(set(canonical_targets) | set(discovered_targets))
    targets = deduplicate_private_refresh_targets(raw_targets)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_GAME_REFRESHES)

    async def refresh_target(user_id: int, game_id: int) -> dict[str, Any]:
        async with semaphore:
            try:
                result = await refresh_accessible_private_intel(
                    user_id=user_id,
                    game_id=game_id,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # one bad game must not stop the scheduler
                LOGGER.warning(
                    "background private refresh failed user=%s game=%s: %s",
                    user_id,
                    game_id,
                    exc,
                    exc_info=True,
                )
                return {
                    "user_id": user_id,
                    "game_id": game_id,
                    "status": "failed",
                    "detail": f"{type(exc).__name__}: {exc}",
                }

            failed = int(result.get("failed", 0))
            LOGGER.info(
                "background private refresh user=%s game=%s turn=%s "
                "refreshed=%s cached=%s skipped=%s failed=%s",
                user_id,
                game_id,
                result.get("turn"),
                result.get("refreshed"),
                result.get("cached"),
                result.get("skipped"),
                failed,
            )
            return {
                "user_id": user_id,
                "game_id": game_id,
                "status": "partial" if failed else "ok",
                "result": result,
            }

    results = await asyncio.gather(
        *(refresh_target(user_id, game_id) for user_id, game_id in targets)
    )
    return {
        "canonical_targets": len(canonical_targets),
        "discovered_targets": len(discovered_targets),
        "discovery_accounts": int(discovery["accounts"]),
        "discovery_failures": int(discovery["failures"]),
        "remote_games_seen": int(discovery["remote_games_seen"]),
        "candidate_games_seen": int(discovery["candidate_games_seen"]),
        "raw_targets": len(raw_targets),
        "targets": len(targets),
        "deduplicated": len(raw_targets) - len(targets),
        "results": results,
    }


async def background_private_refresh_loop() -> None:
    """Refresh all active games forever, independently of the frontend.

    The scheduler probes the intended private transport before fan-out. When
    the Windows/WSL proxy bridge is unavailable, the iteration is skipped and
    retried after a short degraded interval. This avoids timeout storms while
    recovering automatically soon after the bridge returns.
    """

    _PRIVATE_REFRESH_HEALTH["scheduler_running"] = True
    LOGGER.info(
        "background private refresh scheduler started "
        "startup_delay=%ss interval=%ss degraded_retry=%ss",
        BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS,
        BACKGROUND_REFRESH_INTERVAL_SECONDS,
        BACKGROUND_REFRESH_DEGRADED_RETRY_SECONDS,
    )

    try:
        await asyncio.sleep(BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS)
        while True:
            sleep_seconds = BACKGROUND_REFRESH_INTERVAL_SECONDS
            started_at = _utc_iso()
            _PRIVATE_REFRESH_HEALTH.update(
                {
                    "last_iteration_started_at": started_at,
                    "last_iteration_status": "running",
                }
            )

            try:
                transport_ok, transport = await probe_background_private_transport()
                if not transport_ok:
                    sleep_seconds = BACKGROUND_REFRESH_DEGRADED_RETRY_SECONDS
                    completed_at = _utc_iso()
                    _PRIVATE_REFRESH_HEALTH.update(
                        {
                            "last_iteration_completed_at": completed_at,
                            "last_iteration_status": "transport_down",
                            "last_summary": None,
                        }
                    )
                    LOGGER.warning(
                        "background private refresh transport unavailable "
                        "route=%s error=%s retry_in=%ss",
                        _PRIVATE_REFRESH_HEALTH.get("transport_route"),
                        transport.get("detail"),
                        sleep_seconds,
                    )
                else:
                    summary = await refresh_all_running_private_intel_once()
                    partial_count = sum(
                        item.get("status") == "partial"
                        for item in summary.get("results", [])
                    )
                    failed_count = sum(
                        item.get("status") == "failed"
                        for item in summary.get("results", [])
                    )
                    discovery_failures = int(summary.get("discovery_failures", 0))
                    iteration_status = (
                        "ok"
                        if partial_count == 0
                        and failed_count == 0
                        and discovery_failures == 0
                        else "partial"
                    )
                    completed_at = _utc_iso()
                    compact_summary = {
                        "canonical_targets": int(summary.get("canonical_targets", 0)),
                        "discovered_targets": int(summary.get("discovered_targets", 0)),
                        "discovery_failures": discovery_failures,
                        "targets": int(summary.get("targets", 0)),
                        "partial_targets": partial_count,
                        "failed_targets": failed_count,
                    }
                    _PRIVATE_REFRESH_HEALTH.update(
                        {
                            "last_iteration_completed_at": completed_at,
                            "last_iteration_status": iteration_status,
                            "last_summary": compact_summary,
                        }
                    )
                    if iteration_status == "ok":
                        _PRIVATE_REFRESH_HEALTH["last_success_at"] = completed_at

                    LOGGER.info(
                        "background private refresh iteration complete "
                        "canonical_targets=%s discovered_targets=%s "
                        "discovery_failures=%s raw_targets=%s targets=%s "
                        "deduplicated=%s partial_targets=%s failed_targets=%s",
                        summary.get("canonical_targets", 0),
                        summary.get("discovered_targets", 0),
                        discovery_failures,
                        summary.get("raw_targets", 0),
                        summary.get("targets", 0),
                        summary.get("deduplicated", 0),
                        partial_count,
                        failed_count,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                completed_at = _utc_iso()
                _PRIVATE_REFRESH_HEALTH.update(
                    {
                        "last_iteration_completed_at": completed_at,
                        "last_iteration_status": "failed",
                        "last_summary": None,
                    }
                )
                LOGGER.exception(
                    "background private refresh iteration failed: %s",
                    exc,
                )

            await asyncio.sleep(sleep_seconds)
    finally:
        _PRIVATE_REFRESH_HEALTH["scheduler_running"] = False


async def cancel_background_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
