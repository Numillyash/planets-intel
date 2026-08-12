from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
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


def get_accessible_combined_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    """Combine latest factual snapshots from every account the user may see.

    This includes all active linked accounts owned by the local Intel Client
    user plus active mutually-approved dashboard-share peers. The selected
    linked account remains the primary observer only for UI identity; it does
    not restrict the set of factual sources in combined mode.
    """

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
            snapshot = _load_latest_snapshot(
                session,
                account=account,
                game_id=game_id,
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
            "turn": max(snapshot.batch.turn for snapshot in snapshots),
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
