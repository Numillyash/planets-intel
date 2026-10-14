from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.planets_account import PlanetsAccount
from app.services.combined_intel import (
    _Snapshot,
    _load_latest_snapshot,
    _merge_planets,
    _merge_ships,
    _merge_starbases,
    _merge_stellar_cartography,
)
from app.services.intel_access import accessible_intel_accounts


def _select_live_snapshots(
    snapshots: list[_Snapshot],
    *,
    linked_account_id: int,
    current_turn: int,
) -> tuple[list[_Snapshot], _Snapshot | None]:
    """Separate live aggregation sources from primary observer identity.

    A linked observer can remain useful historical evidence after death/removal,
    but an older private batch must not be injected into the current-turn
    combined map. Only batches captured for the current canonical turn may
    contribute live entities.

    The primary observer's latest snapshot is retained separately for identity
    metadata so a dead/archive primary observer can still open a current
    combined view supplied by another authorized current observer.
    """

    primary_snapshot: _Snapshot | None = None
    live: list[_Snapshot] = []

    for snapshot in snapshots:
        if snapshot.account.id == linked_account_id:
            primary_snapshot = snapshot
        if snapshot.batch.turn == current_turn:
            live.append(snapshot)

    return live, primary_snapshot


def get_accessible_combined_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    """Combine latest factual snapshots from every account the user may see."""

    with SessionLocal() as session:
        primary = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if primary is None:
            return None

    accessible = accessible_intel_accounts(user_id=user_id, game_id=game_id, linked_account_id=linked_account_id)
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
        current_turn = session.execute(
            select(Game.current_turn).where(Game.id == game_id)
        ).scalar_one_or_none()
        if current_turn is None:
            return None

        latest_snapshots: list[_Snapshot] = []

        for account in accounts:
            snapshot = _load_latest_snapshot(
                session,
                account=account,
                game_id=game_id,
            )
            if snapshot is not None:
                latest_snapshots.append(snapshot)

        snapshots, primary_snapshot = _select_live_snapshots(
            latest_snapshots,
            linked_account_id=linked_account_id,
            current_turn=int(current_turn),
        )

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
            "minefield": 0,
        }
        for item in stellar_cartography:
            feature_type = item["feature_type"]
            if feature_type in feature_counts:
                feature_counts[feature_type] += 1

        return {
            "mode": "combined",
            "aggregation_policy": "freshest_field_union",
            "game_id": game_id,
            "turn": int(current_turn),
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
                "minefields": feature_counts["minefield"],
            },
            "planets": planets,
            "ships": ships,
            "starbases": starbases,
            "stellar_cartography": stellar_cartography,
        }
