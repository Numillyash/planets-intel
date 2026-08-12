import asyncio
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.models.stellar_cartography_observation import (
    StellarCartographyObservation,
)
from app.planetsnu.client import PlanetsNuError
from app.services.combined_intel import (
    _Snapshot,
    _merge_planets,
    _merge_ships,
    _merge_starbases,
    _merge_stellar_cartography,
)
from app.services.intel_access import accessible_intel_accounts
from app.services.private_sync import (
    PrivateSyncError,
    PrivateSyncTransportError,
    sync_private_game,
)


MAX_CONCURRENT_HISTORICAL_LOADS = 2


def _owned_primary_account(
    *,
    user_id: int,
    linked_account_id: int,
) -> PlanetsAccount | None:
    with SessionLocal() as session:
        return session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()


def _load_snapshot_for_turn(
    session,
    *,
    account: PlanetsAccount,
    game_id: int,
    turn: int,
) -> _Snapshot | None:
    batch = session.execute(
        select(PrivateObservationBatch)
        .where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.observer_planets_account_id
            == account.id,
            PrivateObservationBatch.turn == turn,
        )
        .order_by(
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    if batch is None:
        return None

    planets = list(
        session.execute(
            select(PlanetObservation)
            .where(PlanetObservation.batch_id == batch.id)
            .order_by(PlanetObservation.planet_id)
        ).scalars().all()
    )
    ships = list(
        session.execute(
            select(ShipObservation)
            .where(ShipObservation.batch_id == batch.id)
            .order_by(ShipObservation.ship_id)
        ).scalars().all()
    )
    starbases = list(
        session.execute(
            select(StarbaseObservation)
            .where(StarbaseObservation.batch_id == batch.id)
            .order_by(StarbaseObservation.starbase_id)
        ).scalars().all()
    )
    stellar_cartography = list(
        session.execute(
            select(StellarCartographyObservation)
            .where(StellarCartographyObservation.batch_id == batch.id)
            .order_by(
                StellarCartographyObservation.feature_type,
                StellarCartographyObservation.feature_id,
            )
        ).scalars().all()
    )

    return _Snapshot(
        account=account,
        batch=batch,
        planets=planets,
        ships=ships,
        starbases=starbases,
        stellar_cartography=stellar_cartography,
    )


def get_combined_private_intel_turn(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, Any] | None:
    if turn <= 0:
        return None

    primary = _owned_primary_account(
        user_id=user_id,
        linked_account_id=linked_account_id,
    )
    if primary is None:
        return None

    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids:
        return None

    with SessionLocal() as session:
        accounts = list(
            session.execute(
                select(PlanetsAccount)
                .where(
                    PlanetsAccount.id.in_(accessible_ids),
                    PlanetsAccount.is_active.is_(True),
                )
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )

        snapshots: list[_Snapshot] = []
        primary_snapshot: _Snapshot | None = None

        for account in accounts:
            snapshot = _load_snapshot_for_turn(
                session,
                account=account,
                game_id=game_id,
                turn=turn,
            )
            if snapshot is None:
                continue
            snapshots.append(snapshot)
            if account.id == linked_account_id:
                primary_snapshot = snapshot

        if primary_snapshot is None or not snapshots:
            return None

        planets = _merge_planets(snapshots)
        ships = _merge_ships(snapshots)
        starbases = _merge_starbases(snapshots)
        stellar_cartography = _merge_stellar_cartography(snapshots)

        feature_counts = {
            "nebula": 0,
            "ion_storm": 0,
            "star_cluster": 0,
        }
        for item in stellar_cartography:
            feature_type = item["feature_type"]
            if feature_type in feature_counts:
                feature_counts[feature_type] += 1

        return {
            "mode": "combined",
            "aggregation_policy": "freshest_field_union",
            "game_id": game_id,
            "turn": turn,
            "primary_observer": {
                "linked_account_id": primary.id,
                "planets_account_id": primary.planets_account_id,
                "planets_username": primary.planets_username,
                "player_slot_id": primary_snapshot.batch.source_player_slot_id,
                "is_active": primary.is_active,
            },
            "sources": [
                {
                    "linked_account_id": snapshot.account.id,
                    "planets_account_id": snapshot.account.planets_account_id,
                    "planets_username": snapshot.account.planets_username,
                    "player_slot_id": snapshot.batch.source_player_slot_id,
                    "batch_id": snapshot.batch.id,
                    "turn": snapshot.batch.turn,
                    "source": snapshot.batch.source,
                    "observed_at": snapshot.batch.observed_at,
                }
                for snapshot in snapshots
            ],
            "counts": {
                "planets": len(planets),
                "ships": len(ships),
                "starbases": len(starbases),
                "nebulas": feature_counts["nebula"],
                "ion_storms": feature_counts["ion_storm"],
                "star_clusters": feature_counts["star_cluster"],
            },
            "planets": planets,
            "ships": ships,
            "starbases": starbases,
            "stellar_cartography": stellar_cartography,
        }


def historical_intel_status(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    primary = _owned_primary_account(
        user_id=user_id,
        linked_account_id=linked_account_id,
    )
    if primary is None:
        return None

    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = [account.id for account in accessible]

    with SessionLocal() as session:
        game = session.execute(
            select(Game).where(Game.id == game_id)
        ).scalar_one_or_none()
        if game is None:
            return None

        rows = session.execute(
            select(
                PrivateObservationBatch.observer_planets_account_id,
                PrivateObservationBatch.turn,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
            )
            .distinct()
            .order_by(
                PrivateObservationBatch.observer_planets_account_id,
                PrivateObservationBatch.turn,
            )
        ).all() if accessible_ids else []

    turns_by_account: dict[int, set[int]] = {
        account.id: set()
        for account in accessible
    }
    for account_id, turn in rows:
        turns_by_account.setdefault(account_id, set()).add(turn)

    union_turns = sorted(
        set().union(*turns_by_account.values())
        if turns_by_account
        else set()
    )
    complete_turns = sorted(
        set.intersection(*turns_by_account.values())
        if turns_by_account
        and all(turns_by_account.values())
        else set()
    )

    return {
        "game_id": game_id,
        "current_turn": game.current_turn,
        "primary_linked_account_id": linked_account_id,
        "accounts": [
            {
                "linked_account_id": account.id,
                "planets_username": account.planets_username,
                "is_owned": account.is_owned,
                "turns": sorted(turns_by_account.get(account.id, set())),
            }
            for account in accessible
        ],
        "available_turns": union_turns,
        "complete_turns": complete_turns,
    }


def _account_is_current_game_member(
    *,
    game_id: int,
    planets_account_id: int | None,
) -> bool | None:
    if planets_account_id is None:
        return None

    with SessionLocal() as session:
        exists = session.execute(
            select(GamePlayerSlot.slot_id).where(
                GamePlayerSlot.game_id == game_id,
                GamePlayerSlot.account_id == planets_account_id,
            )
        ).scalar_one_or_none()

    return exists is not None


def _has_turn(
    *,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> bool:
    with SessionLocal() as session:
        batch_id = session.execute(
            select(PrivateObservationBatch.id)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id
                == linked_account_id,
                PrivateObservationBatch.turn == turn,
            )
            .limit(1)
        ).scalar_one_or_none()
    return batch_id is not None


async def backfill_historical_turn(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, Any]:
    primary = _owned_primary_account(
        user_id=user_id,
        linked_account_id=linked_account_id,
    )
    if primary is None:
        raise ValueError("Primary linked Planets.nu account not found")

    with SessionLocal() as session:
        game = session.execute(
            select(Game).where(Game.id == game_id)
        ).scalar_one_or_none()

    if game is None:
        raise ValueError("Game is not present in canonical database")
    if turn <= 0 or turn > game.current_turn:
        raise ValueError(
            f"Historical turn must be between 1 and {game.current_turn}"
        )

    accounts = accessible_intel_accounts(user_id=user_id)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_HISTORICAL_LOADS)

    async def load_one(account) -> dict[str, Any]:
        if _has_turn(
            game_id=game_id,
            linked_account_id=account.id,
            turn=turn,
        ):
            return {
                "linked_account_id": account.id,
                "planets_username": account.planets_username,
                "status": "cached",
                "detail": None,
            }

        membership = _account_is_current_game_member(
            game_id=game_id,
            planets_account_id=account.planets_account_id,
        )
        if membership is False:
            return {
                "linked_account_id": account.id,
                "planets_username": account.planets_username,
                "status": "skipped",
                "detail": "linked account is not a current player in this game",
            }

        async with semaphore:
            try:
                result = await sync_private_game(
                    linked_account_id=account.id,
                    game_id=game_id,
                    turn=turn,
                )
            except PrivateSyncTransportError as exc:
                return {
                    "linked_account_id": account.id,
                    "planets_username": account.planets_username,
                    "status": "failed",
                    "detail": str(exc),
                }
            except PrivateSyncError as exc:
                return {
                    "linked_account_id": account.id,
                    "planets_username": account.planets_username,
                    "status": "failed",
                    "detail": str(exc),
                }
            except PlanetsNuError as exc:
                message = str(exc)
                unavailable = "permission" in message.casefold()
                return {
                    "linked_account_id": account.id,
                    "planets_username": account.planets_username,
                    "status": "unavailable" if unavailable else "failed",
                    "detail": message,
                }

        return {
            "linked_account_id": account.id,
            "planets_username": account.planets_username,
            "status": "stored" if result.get("created") else "cached",
            "detail": None,
        }

    results = await asyncio.gather(*(load_one(account) for account in accounts))
    results = sorted(results, key=lambda item: item["linked_account_id"])

    return {
        "game_id": game_id,
        "turn": turn,
        "accounts": len(accounts),
        "stored": sum(item["status"] == "stored" for item in results),
        "cached": sum(item["status"] == "cached" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "unavailable": sum(
            item["status"] == "unavailable" for item in results
        ),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
