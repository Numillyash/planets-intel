from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_player_slot import GamePlayerSlot
from app.models.planet_observation import PlanetObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation


SCHEMA = "planets-intel.validation-observation.v1"


def _players(session, game_id: int) -> list[dict[str, object]]:
    rows = session.execute(
        select(GamePlayerSlot)
        .where(GamePlayerSlot.game_id == game_id)
        .order_by(GamePlayerSlot.slot_id)
    ).scalars()
    return [
        {
            "id": row.slot_id,
            "accountid": row.account_id,
            "username": row.username,
            "raceid": row.race_id,
            "status": row.status,
        }
        for row in rows
    ]


def _payloads(session, model, batch_id: int, order_column) -> list[dict]:
    rows = session.execute(
        select(model)
        .where(model.batch_id == batch_id)
        .order_by(order_column)
    ).scalars()
    return [row.payload for row in rows]


def iter_records(
    *,
    game_id: int,
    observer_planets_account_id: int | None = None,
    source_player_slot_id: int | None = None,
) -> Iterable[dict[str, object]]:
    with SessionLocal() as session:
        players = _players(session, game_id)
        stmt = select(PrivateObservationBatch).where(
            PrivateObservationBatch.game_id == game_id
        )
        if observer_planets_account_id is not None:
            stmt = stmt.where(
                PrivateObservationBatch.observer_planets_account_id
                == observer_planets_account_id
            )
        if source_player_slot_id is not None:
            stmt = stmt.where(
                PrivateObservationBatch.source_player_slot_id
                == source_player_slot_id
            )
        stmt = stmt.order_by(
            PrivateObservationBatch.observer_planets_account_id,
            PrivateObservationBatch.source_player_slot_id,
            PrivateObservationBatch.source,
            PrivateObservationBatch.turn,
            PrivateObservationBatch.id,
        )

        for batch in session.execute(stmt).scalars():
            yield {
                "schema": SCHEMA,
                "game_id": batch.game_id,
                "turn": batch.turn,
                "batch_id": batch.id,
                "observer_planets_account_id": batch.observer_planets_account_id,
                "source_player_slot_id": batch.source_player_slot_id,
                "source": batch.source,
                "snapshot_hash": batch.snapshot_hash,
                "players": players,
                "planets": _payloads(
                    session,
                    PlanetObservation,
                    batch.id,
                    PlanetObservation.planet_id,
                ),
                "ships": _payloads(
                    session,
                    ShipObservation,
                    batch.id,
                    ShipObservation.ship_id,
                ),
                "starbases": _payloads(
                    session,
                    StarbaseObservation,
                    batch.id,
                    StarbaseObservation.starbase_id,
                ),
            }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export sanitized private observations for planets-lab validation."
    )
    parser.add_argument("--game-id", type=int, required=True)
    parser.add_argument("--observer-planets-account-id", type=int)
    parser.add_argument("--source-player-slot-id", type=int)
    args = parser.parse_args()

    count = 0
    turns: set[int] = set()
    streams: set[tuple[int, int, str]] = set()
    for record in iter_records(
        game_id=args.game_id,
        observer_planets_account_id=args.observer_planets_account_id,
        source_player_slot_id=args.source_player_slot_id,
    ):
        print(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        count += 1
        turns.add(int(record["turn"]))
        streams.add(
            (
                int(record["observer_planets_account_id"]),
                int(record["source_player_slot_id"]),
                str(record["source"]),
            )
        )

    print(
        json.dumps(
            {
                "game_id": args.game_id,
                "records": count,
                "turns": len(turns),
                "streams": len(streams),
                "min_turn": min(turns) if turns else None,
                "max_turn": max(turns) if turns else None,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
