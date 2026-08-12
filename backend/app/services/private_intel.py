from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.models.stellar_cartography_observation import (
    StellarCartographyObservation,
)
from app.services.payload_safety import sanitize_observation_payload


def _serialize_batch(
    session: Session,
    *,
    account: PlanetsAccount,
    batch: PrivateObservationBatch,
) -> dict[str, Any]:
    planets = session.execute(
        select(PlanetObservation)
        .where(PlanetObservation.batch_id == batch.id)
        .order_by(PlanetObservation.planet_id)
    ).scalars().all()

    ships = session.execute(
        select(ShipObservation)
        .where(ShipObservation.batch_id == batch.id)
        .order_by(ShipObservation.ship_id)
    ).scalars().all()

    starbases = session.execute(
        select(StarbaseObservation)
        .where(StarbaseObservation.batch_id == batch.id)
        .order_by(StarbaseObservation.starbase_id)
    ).scalars().all()

    stellar_cartography = session.execute(
        select(StellarCartographyObservation)
        .where(StellarCartographyObservation.batch_id == batch.id)
        .order_by(
            StellarCartographyObservation.feature_type,
            StellarCartographyObservation.feature_id,
        )
    ).scalars().all()

    feature_counts = {
        "nebula": 0,
        "ion_storm": 0,
        "star_cluster": 0,
    }
    for item in stellar_cartography:
        if item.feature_type in feature_counts:
            feature_counts[item.feature_type] += 1

    return {
        "game_id": batch.game_id,
        "turn": batch.turn,
        "observer": {
            "linked_account_id": account.id,
            "planets_account_id": account.planets_account_id,
            "planets_username": account.planets_username,
            "player_slot_id": batch.source_player_slot_id,
            "is_active": account.is_active,
        },
        "observation": {
            "batch_id": batch.id,
            "source": batch.source,
            "snapshot_hash": batch.snapshot_hash,
            # This timestamp means when Intel Client retrieved/persisted the
            # turn. It is deliberately not treated as the historical host time.
            "observed_at": batch.observed_at,
        },
        "counts": {
            "planets": len(planets),
            "ships": len(ships),
            "starbases": len(starbases),
            "nebulas": feature_counts["nebula"],
            "ion_storms": feature_counts["ion_storm"],
            "star_clusters": feature_counts["star_cluster"],
        },
        "planets": [
            {
                "planet_id": item.planet_id,
                "owner_id": item.owner_id,
                "info_turn": item.info_turn,
                "name": item.name,
                "x": item.x,
                "y": item.y,
                "payload": sanitize_observation_payload(item.payload),
            }
            for item in planets
        ],
        "ships": [
            {
                "ship_id": item.ship_id,
                "owner_id": item.owner_id,
                "info_turn": item.info_turn,
                "hull_id": item.hull_id,
                "name": item.name,
                "x": item.x,
                "y": item.y,
                "warp": item.warp,
                "payload": sanitize_observation_payload(item.payload),
            }
            for item in ships
        ],
        "starbases": [
            {
                "starbase_id": item.starbase_id,
                "planet_id": item.planet_id,
                "race_id": item.race_id,
                "info_turn": item.info_turn,
                "payload": sanitize_observation_payload(item.payload),
            }
            for item in starbases
        ],
        "stellar_cartography": [
            {
                "feature_type": item.feature_type,
                "feature_id": item.feature_id,
                "name": item.name,
                "info_turn": item.info_turn,
                "x": item.x,
                "y": item.y,
                "radius": item.radius,
                "payload": sanitize_observation_payload(item.payload),
            }
            for item in stellar_cartography
        ],
    }


def _get_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int | None,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        query = select(PrivateObservationBatch).where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.observer_planets_account_id
            == linked_account_id,
        )

        if turn is not None:
            query = query.where(
                PrivateObservationBatch.turn == turn
            )

        batch = session.execute(
            query.order_by(
                PrivateObservationBatch.turn.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            ).limit(1)
        ).scalar_one_or_none()

        if batch is None:
            return None

        return _serialize_batch(
            session,
            account=account,
            batch=batch,
        )


def get_latest_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    return _get_private_intel(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=None,
    )


def get_private_intel_turn(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, Any] | None:
    if turn <= 0:
        return None

    return _get_private_intel(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
    )
