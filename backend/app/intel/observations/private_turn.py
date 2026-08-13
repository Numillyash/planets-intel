import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.ion_storm_observation import IonStormObservation
from app.models.planet_observation import PlanetObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation


PRIVATE_TURN_SOURCE = "planets.nu/loadturn"
SENSITIVE_KEYS = frozenset({"apikey", "password", "savekey"})


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
        return [_sanitize(item) for item in value]
    return value


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PrivateTurnObservationError(f"{label} must be an object")
    return value


def _entity_list(
    rst: dict[str, Any],
    name: str,
    *,
    required: bool = True,
) -> list[dict[str, Any]]:
    value = rst.get(name)
    if value is None and not required:
        return []
    if not isinstance(value, list):
        raise PrivateTurnObservationError(f"rst.{name} must be a list")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PrivateTurnObservationError(f"rst.{name}[{index}] must be an object")
        result.append(_sanitize(item))
    return result


def _required_int(raw: dict[str, Any], key: str, label: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrivateTurnObservationError(f"{label}.{key} must be an integer")
    return value


def _optional_int(raw: dict[str, Any], key: str, label: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrivateTurnObservationError(f"{label}.{key} must be an integer or null")
    return value


def _optional_string(raw: dict[str, Any], key: str, label: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PrivateTurnObservationError(f"{label}.{key} must be a string or null")
    return value


def _sort_by_id(records: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    for index, record in enumerate(records):
        _required_int(record, "id", f"{label}[{index}]")
    return sorted(records, key=lambda record: record["id"])


def _snapshot_hash(
    planets: list[dict[str, Any]],
    ships: list[dict[str, Any]],
    starbases: list[dict[str, Any]],
    ionstorms: list[dict[str, Any]],
) -> str:
    canonical = {
        "planets": planets,
        "ships": ships,
        "starbases": starbases,
        "ionstorms": ionstorms,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persist_private_turn(
    session: Session,
    *,
    game_id: int,
    observer_planets_account_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    rst = _require_dict(payload.get("rst"), "rst")
    game = _require_dict(rst.get("game"), "rst.game")
    payload_game_id = _required_int(game, "id", "rst.game")
    if payload_game_id != game_id:
        raise PrivateTurnObservationError("private turn belongs to a different game")
    turn = _required_int(game, "turn", "rst.game")
    player = _require_dict(rst.get("player"), "rst.player")
    source_player_slot_id = _required_int(player, "id", "rst.player")

    planets = _sort_by_id(_entity_list(rst, "planets"), "rst.planets")
    ships = _sort_by_id(_entity_list(rst, "ships"), "rst.ships")
    starbases = _sort_by_id(_entity_list(rst, "starbases"), "rst.starbases")
    ionstorms = _sort_by_id(
        _entity_list(rst, "ionstorms", required=False),
        "rst.ionstorms",
    )

    snapshot_hash = _snapshot_hash(planets, ships, starbases, ionstorms)
    batch_table = PrivateObservationBatch.__table__
    batch_stmt = (
        pg_insert(batch_table)
        .values(
            game_id=game_id,
            turn=turn,
            observer_planets_account_id=observer_planets_account_id,
            source_player_slot_id=source_player_slot_id,
            source=PRIVATE_TURN_SOURCE,
            snapshot_hash=snapshot_hash,
        )
        .on_conflict_do_nothing(constraint="uq_private_observation_snapshot")
        .returning(batch_table.c.id)
    )
    batch_id = session.execute(batch_stmt).scalar_one_or_none()
    created = batch_id is not None
    if not created:
        batch_id = session.execute(
            select(PrivateObservationBatch.id).where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.turn == turn,
                PrivateObservationBatch.observer_planets_account_id == observer_planets_account_id,
                PrivateObservationBatch.source == PRIVATE_TURN_SOURCE,
                PrivateObservationBatch.snapshot_hash == snapshot_hash,
            )
        ).scalar_one()
        return {
            "batch_id": batch_id,
            "created": False,
            "game_id": game_id,
            "turn": turn,
            "source_player_slot_id": source_player_slot_id,
            "snapshot_hash": snapshot_hash,
            "planets": len(planets),
            "ships": len(ships),
            "starbases": len(starbases),
            "ionstorms": len(ionstorms),
        }

    planet_rows = [
        {
            "batch_id": batch_id,
            "planet_id": _required_int(raw, "id", "planet"),
            "owner_id": _optional_int(raw, "ownerid", "planet"),
            "info_turn": _optional_int(raw, "infoturn", "planet"),
            "name": _optional_string(raw, "name", "planet"),
            "x": _optional_int(raw, "x", "planet"),
            "y": _optional_int(raw, "y", "planet"),
            "payload": raw,
        }
        for raw in planets
    ]
    ship_rows = [
        {
            "batch_id": batch_id,
            "ship_id": _required_int(raw, "id", "ship"),
            "owner_id": _optional_int(raw, "ownerid", "ship"),
            "info_turn": _optional_int(raw, "infoturn", "ship"),
            "hull_id": _optional_int(raw, "hullid", "ship"),
            "name": _optional_string(raw, "name", "ship"),
            "x": _optional_int(raw, "x", "ship"),
            "y": _optional_int(raw, "y", "ship"),
            "warp": _optional_int(raw, "warp", "ship"),
            "payload": raw,
        }
        for raw in ships
    ]
    starbase_rows = [
        {
            "batch_id": batch_id,
            "starbase_id": _required_int(raw, "id", "starbase"),
            "planet_id": _optional_int(raw, "planetid", "starbase"),
            "race_id": _optional_int(raw, "raceid", "starbase"),
            "info_turn": _optional_int(raw, "infoturn", "starbase"),
            "payload": raw,
        }
        for raw in starbases
    ]
    storm_rows = [
        {
            "batch_id": batch_id,
            "storm_id": _required_int(raw, "id", "ionstorm"),
            "x": _optional_int(raw, "x", "ionstorm"),
            "y": _optional_int(raw, "y", "ionstorm"),
            "radius": _optional_int(raw, "radius", "ionstorm"),
            "voltage": _optional_int(raw, "voltage", "ionstorm"),
            "warp": _optional_int(raw, "warp", "ionstorm"),
            "heading": _optional_int(raw, "heading", "ionstorm"),
            "is_growing": raw.get("isgrowing") if isinstance(raw.get("isgrowing"), bool) else None,
            "payload": raw,
        }
        for raw in ionstorms
    ]

    if planet_rows:
        session.execute(pg_insert(PlanetObservation.__table__), planet_rows)
    if ship_rows:
        session.execute(pg_insert(ShipObservation.__table__), ship_rows)
    if starbase_rows:
        session.execute(pg_insert(StarbaseObservation.__table__), starbase_rows)
    if storm_rows:
        session.execute(pg_insert(IonStormObservation.__table__), storm_rows)
    session.flush()

    return {
        "batch_id": batch_id,
        "created": True,
        "game_id": game_id,
        "turn": turn,
        "source_player_slot_id": source_player_slot_id,
        "snapshot_hash": snapshot_hash,
        "planets": len(planets),
        "ships": len(ships),
        "starbases": len(starbases),
        "ionstorms": len(ionstorms),
    }
