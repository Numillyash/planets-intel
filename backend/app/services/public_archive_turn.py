"""Non-persistent, strictly public read-only archive turn adapter.

Not a private observation batch. Do not call private_sync, persist_private_turn,
canonical snapshots, private grants or credential decryption from this module.
"""
from __future__ import annotations

from typing import Any

from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.services.payload_safety import (
    sanitize_observation_payload,
    sanitize_ship_observation_payload,
)

STELLAR = (
    ("nebulas", "nebula"),
    ("ionstorms", "ion_storm"),
    ("stars", "star_cluster"),
    ("minefields", "minefield"),
)


class ArchiveNotPublicOrFinished(ValueError):
    pass


class ArchiveSourceMismatch(ValueError):
    pass


def _positive(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _integer(value: Any) -> int | None:
    return value if type(value) is int else None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def assert_finished_public_game(payload: Any, game_id: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ArchiveNotPublicOrFinished("Public game information is unavailable")
    game = payload.get("game")
    if (
        not isinstance(game, dict)
        or _positive(game.get("id")) != game_id
        or game.get("isprivate") is not False
        or _integer(game.get("status")) != 3
        or not isinstance(payload.get("players"), list)
    ):
        raise ArchiveNotPublicOrFinished(
            "Historical turns require a verified finished public game"
        )
    return game


def _entities(rst: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = rst.get(key)
    if not isinstance(values, list):
        raise ArchiveSourceMismatch("Historical rst missing " + key)
    if len(values) > 20000 or any(not isinstance(x, dict) for x in values):
        raise ArchiveSourceMismatch("Invalid historical rst " + key)
    return values


def adapt_finished_public_turn(
    *,
    info: dict[str, Any],
    payload: dict[str, Any],
    game_id: int,
    player_id: int,
    turn: int,
) -> dict[str, Any]:
    info_game = assert_finished_public_game(info, game_id)
    if not 1 <= player_id <= 35 or turn < 1:
        raise ArchiveSourceMismatch("Invalid selected slot or turn")
    if _positive(info_game.get("turn")) is not None and turn > info_game["turn"]:
        raise ArchiveSourceMismatch("Requested turn exceeds final game turn")

    # Source slot is a game slot, not a linked local observer. A replacement
    # may have occupied it at a different time; no identity is inferred.
    if not any(
        isinstance(row, dict) and _positive(row.get("id")) == player_id
        for row in info["players"]
    ):
        raise ArchiveSourceMismatch("Selected slot is not in the public game")

    rst = payload.get("rst")
    if not isinstance(rst, dict):
        raise ArchiveSourceMismatch("No historical rst")
    game = rst.get("game")
    player = rst.get("player")
    if not isinstance(game, dict) or not isinstance(player, dict):
        raise ArchiveSourceMismatch("Historical rst lacks game/player identity")
    if (
        _positive(game.get("id")) != game_id
        or _positive(game.get("turn")) != turn
        or _positive(player.get("id")) != player_id
    ):
        raise ArchiveSourceMismatch("Historical rst identity does not match requested game/slot/turn")

    planets = []
    for row in _entities(rst, "planets"):
        entity_id = _positive(row.get("id"))
        if entity_id is None:
            continue
        planets.append({
            "planet_id": entity_id,
            "owner_id": _positive(row.get("ownerid")),
            "info_turn": _positive(row.get("infoturn")),
            "name": _string(row.get("name")),
            "x": _integer(row.get("x")),
            "y": _integer(row.get("y")),
            "payload": sanitize_observation_payload(row),
        })
    ships = []
    for row in _entities(rst, "ships"):
        entity_id = _positive(row.get("id"))
        if entity_id is None:
            continue
        owner = _positive(row.get("ownerid"))
        ships.append({
            "ship_id": entity_id,
            "owner_id": owner,
            "info_turn": _positive(row.get("infoturn")),
            "hull_id": _positive(row.get("hullid")),
            "name": _string(row.get("name")),
            "x": _integer(row.get("x")),
            "y": _integer(row.get("y")),
            "warp": _integer(row.get("warp")),
            "payload": sanitize_ship_observation_payload(
                row, observer_slot_id=player_id, owner_id=owner,
            ),
        })
    starbases = []
    for row in _entities(rst, "starbases"):
        entity_id = _positive(row.get("id"))
        if entity_id is None:
            continue
        starbases.append({
            "starbase_id": entity_id,
            "planet_id": _positive(row.get("planetid")),
            "race_id": _positive(row.get("raceid")),
            "info_turn": _positive(row.get("infoturn")),
            "payload": sanitize_observation_payload(row),
        })
    features = []
    for source, kind in STELLAR:
        raw = rst.get(source, [])
        if not isinstance(raw, list) or len(raw) > 20000:
            raise ArchiveSourceMismatch("Invalid historical stellar collection")
        for row in raw:
            if not isinstance(row, dict):
                raise ArchiveSourceMismatch("Invalid historical stellar record")
            entity_id = _positive(row.get("id"))
            if entity_id is None:
                continue
            features.append({
                "feature_type": kind,
                "feature_id": entity_id,
                "name": _string(row.get("name")),
                "info_turn": _positive(row.get("infoturn")),
                "x": _integer(row.get("x")),
                "y": _integer(row.get("y")),
                "radius": _integer(row.get("radius")),
                "payload": sanitize_observation_payload(row),
            })
    return {
        "mode": "public_finished_archive",
        "source": "planets.nu/game/loadturn",
        "game_id": game_id,
        "turn": turn,
        "player_slot_id": player_id,
        "counts": {
            "planets": len(planets),
            "ships": len(ships),
            "starbases": len(starbases),
        },
        "planets": planets,
        "ships": ships,
        "starbases": starbases,
        "stellar_cartography": features,
    }


async def fetch_finished_public_turn(
    game_id: int, player_id: int, turn: int,
) -> dict[str, Any]:
    client = PlanetsNuClient()
    info = await client.load_info(game_id)
    game = assert_finished_public_game(info, game_id)
    if (
        not 1 <= player_id <= 35
        or turn <= 0
        or (_positive(game.get("turn")) is not None and turn > game["turn"])
        or not any(
            isinstance(row, dict) and _positive(row.get("id")) == player_id
            for row in info["players"]
        )
    ):
        raise ArchiveSourceMismatch("Invalid archived player slot or turn")
    payload = await client.load_finished_public_turn(
        game_id=game_id, player_id=player_id, turn=turn,
    )
    return adapt_finished_public_turn(
        info=info, payload=payload, game_id=game_id,
        player_id=player_id, turn=turn,
    )
