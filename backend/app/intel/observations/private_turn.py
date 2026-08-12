import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.planet_observation import PlanetObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.models.stellar_cartography_observation import (
    StellarCartographyObservation,
)


PRIVATE_TURN_SOURCE = "planets.nu/loadturn"

SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "password",
        "savekey",
    }
)

STELLAR_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("nebulas", "nebula"),
    ("ionstorms", "ion_storm"),
    ("stars", "star_cluster"),
)


class PrivateTurnObservationError(ValueError):
    pass


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_KEYS
        }

    if isinstance(value, list):
        return [
            _sanitize(item)
            for item in value
        ]

    return value


def _require_dict(
    value: Any,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PrivateTurnObservationError(
            f"{label} must be an object"
        )

    return value


def _require_entity_list(
    rst: dict[str, Any],
    name: str,
) -> list[dict[str, Any]]:
    value = rst.get(name)

    if not isinstance(value, list):
        raise PrivateTurnObservationError(
            f"rst.{name} must be a list"
        )

    result: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PrivateTurnObservationError(
                f"rst.{name}[{index}] must be an object"
            )

        result.append(
            _sanitize(item)
        )

    return result


def _optional_entity_list(
    rst: dict[str, Any],
    name: str,
) -> list[dict[str, Any]]:
    value = rst.get(name, [])

    if value is None:
        return []

    if not isinstance(value, list):
        raise PrivateTurnObservationError(
            f"rst.{name} must be a list when present"
        )

    result: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PrivateTurnObservationError(
                f"rst.{name}[{index}] must be an object"
            )

        result.append(
            _sanitize(item)
        )

    return result


def _required_int(
    raw: dict[str, Any],
    key: str,
    label: str,
) -> int:
    value = raw.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise PrivateTurnObservationError(
            f"{label}.{key} must be an integer"
        )

    return value


def _optional_int(
    raw: dict[str, Any],
    key: str,
    label: str,
) -> int | None:
    value = raw.get(key)

    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise PrivateTurnObservationError(
            f"{label}.{key} must be an integer or null"
        )

    return value


def _optional_string(
    raw: dict[str, Any],
    key: str,
    label: str,
) -> str | None:
    value = raw.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise PrivateTurnObservationError(
            f"{label}.{key} must be a string or null"
        )

    return value


def _sort_by_id(
    records: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    for index, record in enumerate(records):
        _required_int(
            record,
            "id",
            f"{label}[{index}]",
        )

    return sorted(
        records,
        key=lambda record: record["id"],
    )


def _snapshot_hash(
    planets: list[dict[str, Any]],
    ships: list[dict[str, Any]],
    starbases: list[dict[str, Any]],
    stellar_cartography: dict[str, list[dict[str, Any]]],
) -> str:
    canonical = {
        "planets": planets,
        "ships": ships,
        "starbases": starbases,
        "stellar_cartography": stellar_cartography,
    }

    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def persist_private_turn(
    session: Session,
    *,
    game_id: int,
    observer_planets_account_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    rst = _require_dict(
        payload.get("rst"),
        "rst",
    )

    game = _require_dict(
        rst.get("game"),
        "rst.game",
    )

    payload_game_id = _required_int(
        game,
        "id",
        "rst.game",
    )

    if payload_game_id != game_id:
        raise PrivateTurnObservationError(
            "private turn belongs to a different game"
        )

    turn = _required_int(
        game,
        "turn",
        "rst.game",
    )

    player = _require_dict(
        rst.get("player"),
        "rst.player",
    )

    source_player_slot_id = _required_int(
        player,
        "id",
        "rst.player",
    )

    planets = _sort_by_id(
        _require_entity_list(
            rst,
            "planets",
        ),
        "rst.planets",
    )

    ships = _sort_by_id(
        _require_entity_list(
            rst,
            "ships",
        ),
        "rst.ships",
    )

    starbases = _sort_by_id(
        _require_entity_list(
            rst,
            "starbases",
        ),
        "rst.starbases",
    )

    stellar_cartography: dict[str, list[dict[str, Any]]] = {}
    for source_name, feature_type in STELLAR_COLLECTIONS:
        stellar_cartography[feature_type] = _sort_by_id(
            _optional_entity_list(rst, source_name),
            f"rst.{source_name}",
        )

    snapshot_hash = _snapshot_hash(
        planets,
        ships,
        starbases,
        stellar_cartography,
    )

    batch_table = (
        PrivateObservationBatch.__table__
    )

    batch_stmt = (
        pg_insert(batch_table)
        .values(
            game_id=game_id,
            turn=turn,
            observer_planets_account_id=(
                observer_planets_account_id
            ),
            source_player_slot_id=(
                source_player_slot_id
            ),
            source=PRIVATE_TURN_SOURCE,
            snapshot_hash=snapshot_hash,
        )
        .on_conflict_do_nothing(
            constraint=(
                "uq_private_observation_snapshot"
            )
        )
        .returning(batch_table.c.id)
    )

    batch_id = session.execute(
        batch_stmt
    ).scalar_one_or_none()

    created = batch_id is not None

    if not created:
        batch_id = session.execute(
            select(
                PrivateObservationBatch.id
            ).where(
                PrivateObservationBatch.game_id
                == game_id,
                PrivateObservationBatch.turn
                == turn,
                PrivateObservationBatch.observer_planets_account_id
                == observer_planets_account_id,
                PrivateObservationBatch.source
                == PRIVATE_TURN_SOURCE,
                PrivateObservationBatch.snapshot_hash
                == snapshot_hash,
            )
        ).scalar_one()

        return {
            "batch_id": batch_id,
            "created": False,
            "game_id": game_id,
            "turn": turn,
            "source_player_slot_id": (
                source_player_slot_id
            ),
            "snapshot_hash": snapshot_hash,
            "planets": len(planets),
            "ships": len(ships),
            "starbases": len(starbases),
            "nebulas": len(stellar_cartography["nebula"]),
            "ion_storms": len(stellar_cartography["ion_storm"]),
            "star_clusters": len(stellar_cartography["star_cluster"]),
        }

    planet_rows = []

    for raw in planets:
        planet_rows.append(
            {
                "batch_id": batch_id,
                "planet_id": _required_int(
                    raw,
                    "id",
                    "planet",
                ),
                "owner_id": _optional_int(
                    raw,
                    "ownerid",
                    "planet",
                ),
                "info_turn": _optional_int(
                    raw,
                    "infoturn",
                    "planet",
                ),
                "name": _optional_string(
                    raw,
                    "name",
                    "planet",
                ),
                "x": _optional_int(
                    raw,
                    "x",
                    "planet",
                ),
                "y": _optional_int(
                    raw,
                    "y",
                    "planet",
                ),
                "payload": raw,
            }
        )

    ship_rows = []

    for raw in ships:
        ship_rows.append(
            {
                "batch_id": batch_id,
                "ship_id": _required_int(
                    raw,
                    "id",
                    "ship",
                ),
                "owner_id": _optional_int(
                    raw,
                    "ownerid",
                    "ship",
                ),
                "info_turn": _optional_int(
                    raw,
                    "infoturn",
                    "ship",
                ),
                "hull_id": _optional_int(
                    raw,
                    "hullid",
                    "ship",
                ),
                "name": _optional_string(
                    raw,
                    "name",
                    "ship",
                ),
                "x": _optional_int(
                    raw,
                    "x",
                    "ship",
                ),
                "y": _optional_int(
                    raw,
                    "y",
                    "ship",
                ),
                "warp": _optional_int(
                    raw,
                    "warp",
                    "ship",
                ),
                "payload": raw,
            }
        )

    starbase_rows = []

    for raw in starbases:
        starbase_rows.append(
            {
                "batch_id": batch_id,
                "starbase_id": _required_int(
                    raw,
                    "id",
                    "starbase",
                ),
                "planet_id": _optional_int(
                    raw,
                    "planetid",
                    "starbase",
                ),
                "race_id": _optional_int(
                    raw,
                    "raceid",
                    "starbase",
                ),
                "info_turn": _optional_int(
                    raw,
                    "infoturn",
                    "starbase",
                ),
                "payload": raw,
            }
        )

    stellar_rows = []

    for feature_type, records in stellar_cartography.items():
        for raw in records:
            label = feature_type.replace("_", " ")
            stellar_rows.append(
                {
                    "batch_id": batch_id,
                    "feature_type": feature_type,
                    "feature_id": _required_int(
                        raw,
                        "id",
                        label,
                    ),
                    "name": _optional_string(
                        raw,
                        "name",
                        label,
                    ),
                    "info_turn": _optional_int(
                        raw,
                        "infoturn",
                        label,
                    ),
                    "x": _optional_int(
                        raw,
                        "x",
                        label,
                    ),
                    "y": _optional_int(
                        raw,
                        "y",
                        label,
                    ),
                    "radius": _optional_int(
                        raw,
                        "radius",
                        label,
                    ),
                    "payload": raw,
                }
            )

    if planet_rows:
        session.execute(
            pg_insert(
                PlanetObservation.__table__
            ),
            planet_rows,
        )

    if ship_rows:
        session.execute(
            pg_insert(
                ShipObservation.__table__
            ),
            ship_rows,
        )

    if starbase_rows:
        session.execute(
            pg_insert(
                StarbaseObservation.__table__
            ),
            starbase_rows,
        )

    if stellar_rows:
        session.execute(
            pg_insert(
                StellarCartographyObservation.__table__
            ),
            stellar_rows,
        )

    session.flush()

    return {
        "batch_id": batch_id,
        "created": True,
        "game_id": game_id,
        "turn": turn,
        "source_player_slot_id": (
            source_player_slot_id
        ),
        "snapshot_hash": snapshot_hash,
        "planets": len(planets),
        "ships": len(ships),
        "starbases": len(starbases),
        "nebulas": len(stellar_cartography["nebula"]),
        "ion_storms": len(stellar_cartography["ion_storm"]),
        "star_clusters": len(stellar_cartography["star_cluster"]),
    }
