import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func, or_, select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.planetsnu.client import PlanetsNuError
from app.services.intel_sharing import active_dashboard_peer_account_ids
from app.services.private_sync import (
    PrivateSyncError,
    PrivateSyncTransportError,
    sync_private_game,
)
from app.services.public_sync import sync_public_game


MIN_REFRESH_INTERVAL = timedelta(minutes=4, seconds=30)
MAX_CONCURRENT_PRIVATE_REFRESHES = 3


def _accessible_accounts(user_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        owned = list(
            session.execute(
                select(PlanetsAccount)
                .where(
                    PlanetsAccount.user_id == user_id,
                    PlanetsAccount.is_active.is_(True),
                )
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )

    owned_ids = {account.id for account in owned}
    peer_ids: set[int] = set()
    for account_id in owned_ids:
        peer_ids.update(
            active_dashboard_peer_account_ids(
                linked_account_id=account_id,
            )
        )

    all_ids = sorted(owned_ids | peer_ids)
    if not all_ids:
        return []

    with SessionLocal() as session:
        accounts = list(
            session.execute(
                select(PlanetsAccount)
                .where(
                    PlanetsAccount.id.in_(all_ids),
                    PlanetsAccount.is_active.is_(True),
                )
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )

        return [
            {
                "id": account.id,
                "planets_username": account.planets_username,
                "planets_account_id": account.planets_account_id,
                "is_owned": account.id in owned_ids,
            }
            for account in accounts
        ]


def accessible_refresh_account_ids(user_id: int) -> tuple[int, ...]:
    """Return the linked observer ids a local user may refresh/share."""

    return tuple(int(account["id"]) for account in _accessible_accounts(user_id))


def _latest_batch(
    *,
    linked_account_id: int,
    game_id: int,
) -> PrivateObservationBatch | None:
    with SessionLocal() as session:
        return session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id
                == linked_account_id,
            )
            .order_by(
                PrivateObservationBatch.turn.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()


def _canonical_current_turn(game_id: int) -> int | None:
    with SessionLocal() as session:
        value = session.execute(
            select(Game.current_turn).where(Game.id == game_id)
        ).scalar_one_or_none()
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


async def _resolve_refresh_turn(game_id: int) -> tuple[int, dict[str, Any]]:
    """Resolve the turn without making public API availability a private-sync gate.

    A public sync is preferred because it keeps canonical game metadata fresh.
    During a public transport/API outage, however, a previously synchronized
    canonical Game row is sufficient to throttle current private loadturn
    refreshes. Each private sync still asks Planets.nu for the current turn and
    validates the returned private payload independently.
    """

    try:
        public_result = await sync_public_game(game_id)
        return int(public_result["turn"]), {
            "status": "refreshed",
            "source": "planetsnu-public",
            "detail": None,
        }
    except (httpx.TransportError, PlanetsNuError) as exc:
        cached_turn = _canonical_current_turn(game_id)
        if cached_turn is None:
            raise
        return cached_turn, {
            "status": "canonical-fallback",
            "source": "canonical-cache",
            "detail": (
                "public synchronization unavailable; private loadturn refresh "
                f"continued using cached turn {cached_turn} for throttling "
                f"({type(exc).__name__})"
            ),
        }


def _is_account_in_game(
    *,
    planets_account_id: int | None,
    planets_username: str,
    game_id: int,
) -> bool | None:
    """Match a linked observer to the canonical roster conservatively.

    Planets.nu may replace account ids with sentinel/zero values after a player
    dies. The canonical slot username is therefore an allowed fallback, matching
    the identity policy already used by the game picker/background target scan.
    If neither identity field is usable, return ``None`` so the caller does not
    turn unknown membership into a false negative.
    """

    normalized_username = planets_username.strip().casefold()
    predicates = []
    if planets_account_id is not None and planets_account_id > 0:
        predicates.append(GamePlayerSlot.account_id == planets_account_id)
    if normalized_username:
        predicates.append(func.lower(GamePlayerSlot.username) == normalized_username)
    if not predicates:
        return None

    with SessionLocal() as session:
        slot = session.execute(
            select(GamePlayerSlot.slot_id).where(
                GamePlayerSlot.game_id == game_id,
                or_(*predicates),
            )
        ).scalar_one_or_none()

    return slot is not None


def _is_recent_current_batch(
    batch: PrivateObservationBatch | None,
    *,
    current_turn: int,
    now: datetime,
) -> bool:
    if batch is None or batch.turn < current_turn:
        return False

    observed_at = batch.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    return now - observed_at <= MIN_REFRESH_INTERVAL


async def refresh_accessible_private_intel(
    *,
    user_id: int,
    game_id: int,
) -> dict[str, Any]:
    """Refresh every private observer the user is allowed to combine.

    Owned linked accounts are always eligible. Accounts owned by another
    local user are eligible only through an active, mutually approved
    dashboard intel share. The combined result itself remains a read-time
    aggregation; this service only refreshes observer-specific factual
    snapshots.

    Public game synchronization is best-effort here. A public outage must not
    prevent current private loadturn observations from refreshing when a
    canonical game row already exists locally.
    """

    current_turn, public_sync = await _resolve_refresh_turn(game_id)
    accounts = _accessible_accounts(user_id)
    now = datetime.now(timezone.utc)

    immediate_results: list[dict[str, Any]] = []
    refresh_candidates: list[dict[str, Any]] = []

    for account in accounts:
        membership = _is_account_in_game(
            planets_account_id=account["planets_account_id"],
            planets_username=account["planets_username"],
            game_id=game_id,
        )

        if membership is False:
            immediate_results.append(
                {
                    "linked_account_id": account["id"],
                    "planets_username": account["planets_username"],
                    "status": "skipped",
                    "detail": "linked account is not a player in this game",
                }
            )
            continue

        latest = _latest_batch(
            linked_account_id=account["id"],
            game_id=game_id,
        )
        if _is_recent_current_batch(
            latest,
            current_turn=current_turn,
            now=now,
        ):
            immediate_results.append(
                {
                    "linked_account_id": account["id"],
                    "planets_username": account["planets_username"],
                    "status": "cached",
                    "detail": "current snapshot is younger than 4.5 minutes",
                }
            )
            continue

        refresh_candidates.append(account)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PRIVATE_REFRESHES)

    async def refresh_one(account: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            try:
                result = await sync_private_game(
                    linked_account_id=account["id"],
                    game_id=game_id,
                )
            except PrivateSyncTransportError as exc:
                return {
                    "linked_account_id": account["id"],
                    "planets_username": account["planets_username"],
                    "status": "failed",
                    "detail": str(exc),
                }
            except PrivateSyncError as exc:
                return {
                    "linked_account_id": account["id"],
                    "planets_username": account["planets_username"],
                    "status": "failed",
                    "detail": str(exc),
                }
            except PlanetsNuError as exc:
                return {
                    "linked_account_id": account["id"],
                    "planets_username": account["planets_username"],
                    "status": "failed",
                    "detail": str(exc),
                }

            return {
                "linked_account_id": account["id"],
                "planets_username": account["planets_username"],
                "status": "refreshed" if result.get("created") else "cached",
                "detail": None,
            }

    refreshed_results = await asyncio.gather(
        *(refresh_one(account) for account in refresh_candidates)
    )
    results = sorted(
        [*immediate_results, *refreshed_results],
        key=lambda item: int(item["linked_account_id"]),
    )

    return {
        "game_id": game_id,
        "turn": current_turn,
        "public_sync": public_sync,
        "accounts": len(accounts),
        "refreshed": sum(item["status"] == "refreshed" for item in results),
        "cached": sum(item["status"] == "cached" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
