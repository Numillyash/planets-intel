from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from sqlalchemy import func, or_, select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.services.private_refresh import refresh_accessible_private_intel


# Uvicorn installs handlers for its own logger hierarchy, while arbitrary
# module loggers can stay below the configured output level. Background
# collection is operational infrastructure, so route its INFO diagnostics
# through uvicorn.error to make successful scheduler passes observable in
# container logs without promoting them to warnings.
LOGGER = logging.getLogger("uvicorn.error")

BACKGROUND_REFRESH_INTERVAL_SECONDS = 5 * 60
BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS = 15
MAX_CONCURRENT_GAME_REFRESHES = 2


def running_private_refresh_targets() -> list[tuple[int, int]]:
    """Return unique ``(local_user_id, game_id)`` background refresh targets.

    Membership is matched against canonical game slots by verified external
    account id, with canonical username as a conservative fallback for dead or
    sentinel-shaped player records. ``refresh_accessible_private_intel`` then
    refreshes every observer that user is allowed to combine for that game.

    Planets.nu games can remain cached locally as ``Joining`` after the host has
    already started producing turns. Include both ``Joining`` and ``Running``
    here: the first public sync for such a target refreshes the canonical game
    status before private loadturn collection. Explicitly finished games remain
    excluded from the periodic collector.

    This intentionally does not depend on any browser session or currently
    selected observer/game.
    """

    with SessionLocal() as session:
        rows = session.execute(
            select(
                PlanetsAccount.user_id,
                GamePlayerSlot.game_id,
            )
            .join(
                GamePlayerSlot,
                or_(
                    GamePlayerSlot.account_id == PlanetsAccount.planets_account_id,
                    func.lower(GamePlayerSlot.username)
                    == func.lower(PlanetsAccount.planets_username),
                ),
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


async def refresh_all_running_private_intel_once() -> dict[str, Any]:
    targets = running_private_refresh_targets()
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
        "targets": len(targets),
        "results": results,
    }


async def background_private_refresh_loop() -> None:
    """Refresh all active games forever, independently of the frontend."""

    LOGGER.info(
        "background private refresh scheduler started startup_delay=%ss interval=%ss",
        BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS,
        BACKGROUND_REFRESH_INTERVAL_SECONDS,
    )
    await asyncio.sleep(BACKGROUND_REFRESH_STARTUP_DELAY_SECONDS)
    while True:
        try:
            summary = await refresh_all_running_private_intel_once()
            LOGGER.info(
                "background private refresh iteration complete targets=%s",
                summary.get("targets", 0),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("background private refresh iteration failed")

        await asyncio.sleep(BACKGROUND_REFRESH_INTERVAL_SECONDS)


async def cancel_background_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
