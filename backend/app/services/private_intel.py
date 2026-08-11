from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation


def get_latest_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id
                == linked_account_id,
                PlanetsAccount.user_id
                == user_id,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        batch = session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id
                == game_id,
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

        if batch is None:
            return None

        planets = session.execute(
            select(PlanetObservation)
            .where(
                PlanetObservation.batch_id
                == batch.id
            )
            .order_by(
                PlanetObservation.planet_id
            )
        ).scalars().all()

        ships = session.execute(
            select(ShipObservation)
            .where(
                ShipObservation.batch_id
                == batch.id
            )
            .order_by(
                ShipObservation.ship_id
            )
        ).scalars().all()

        starbases = session.execute(
            select(StarbaseObservation)
            .where(
                StarbaseObservation.batch_id
                == batch.id
            )
            .order_by(
                StarbaseObservation.starbase_id
            )
        ).scalars().all()

        return {
            "game_id": game_id,
            "turn": batch.turn,

            "observer": {
                "linked_account_id": (
                    account.id
                ),
                "planets_account_id": (
                    account.planets_account_id
                ),
                "planets_username": (
                    account.planets_username
                ),
                "player_slot_id": (
                    batch.source_player_slot_id
                ),
                "is_active": (
                    account.is_active
                ),
            },

            "observation": {
                "batch_id": batch.id,
                "source": batch.source,
                "snapshot_hash": (
                    batch.snapshot_hash
                ),
                "observed_at": (
                    batch.observed_at
                ),
            },

            "counts": {
                "planets": len(planets),
                "ships": len(ships),
                "starbases": len(starbases),
            },

            "planets": [
                {
                    "planet_id": item.planet_id,
                    "owner_id": item.owner_id,
                    "info_turn": item.info_turn,
                    "name": item.name,
                    "x": item.x,
                    "y": item.y,
                    "payload": item.payload,
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
                    "payload": item.payload,
                }
                for item in ships
            ],

            "starbases": [
                {
                    "starbase_id": (
                        item.starbase_id
                    ),
                    "planet_id": item.planet_id,
                    "race_id": item.race_id,
                    "info_turn": item.info_turn,
                    "payload": item.payload,
                }
                for item in starbases
            ],
        }
