from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


def _side_for_ship(payload: dict[str, Any], ship_id: int) -> str | None:
    for side_name in ("left", "right"):
        side = payload.get(side_name)
        if not isinstance(side, dict) or side.get("objectid") != ship_id:
            continue
        hull_id = side.get("hullid")
        if isinstance(hull_id, int) and not isinstance(hull_id, bool) and hull_id > 0:
            return side_name
    return None


def _state(replay: dict[str, Any], side_name: str, *, turn: int, vcr_id: int, ship_id: int) -> dict[str, Any] | None:
    side = replay.get(side_name)
    if not isinstance(side, dict):
        return None
    return {
        "turn": turn,
        "vcr_id": vcr_id,
        "ship_id": ship_id,
        "post_combat_torpedoes": side.get("torpedoes"),
        "post_combat_fighters": side.get("fighters"),
        "post_combat_shield": side.get("shield"),
        "post_combat_damage": side.get("damage"),
        "post_combat_crew": side.get("crew"),
        "survived": side.get("survived"),
        "destroyed": side.get("destroyed"),
        "captured": side.get("captured"),
        "source": "deterministic_vcr_replay",
        "basis": replay.get("basis"),
        "engine": replay.get("engine"),
        "cycles": replay.get("cycles"),
        "final_seed": replay.get("final_seed"),
    }


def _inputs(user_id: int, game_id: int, through_turn: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    accessible_ids = {account.id for account in accessible_intel_accounts(user_id=user_id)}
    if not accessible_ids:
        return [], [], {}, []

    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        if catalog is None:
            return [], [], {}, []

        rows = session.execute(
            select(CombatObservation, PrivateObservationBatch)
            .join(PrivateObservationBatch, PrivateObservationBatch.id == CombatObservation.batch_id)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                CombatObservation.battle_turn <= through_turn,
            )
            .order_by(
                CombatObservation.battle_turn.desc(),
                CombatObservation.vcr_id.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).all()

        records = [
            {
                "turn": int(combat.battle_turn),
                "vcr_id": int(combat.vcr_id),
                "payload": dict(combat.payload) if isinstance(combat.payload, dict) else {},
            }
            for combat, _batch in rows
        ]
        return list(catalog.beams), list(catalog.torpedos), dict(catalog.settings), records


def replay_state_map(*, user_id: int, game_id: int, turn: int) -> dict[tuple[int, int], dict[str, Any]]:
    beams, torpedoes, settings, records = _inputs(user_id, game_id, turn)
    result: dict[tuple[int, int], dict[str, Any]] = {}
    seen: set[tuple[int, int]] = set()

    for record in records:
        if record["turn"] != turn:
            continue
        battle_key = (record["turn"], record["vcr_id"])
        if battle_key in seen:
            continue
        seen.add(battle_key)
        payload = record["payload"]
        try:
            replay = replay_nuhost_from_nu_catalog(payload, beams=beams, torpedoes=torpedoes, settings=settings)
        except ReplayUnsupported:
            continue
        for side_name in ("left", "right"):
            side = payload.get(side_name)
            if not isinstance(side, dict):
                continue
            ship_id = side.get("objectid")
            if not isinstance(ship_id, int) or isinstance(ship_id, bool) or _side_for_ship(payload, ship_id) != side_name:
                continue
            state = _state(replay, side_name, turn=turn, vcr_id=record["vcr_id"], ship_id=ship_id)
            if state is not None:
                result[(record["vcr_id"], ship_id)] = state
    return result


def latest_ship_replay_state(*, user_id: int, game_id: int, ship_id: int, through_turn: int) -> dict[str, Any] | None:
    beams, torpedoes, settings, records = _inputs(user_id, game_id, through_turn)
    seen: set[tuple[int, int]] = set()

    for record in records:
        battle_key = (record["turn"], record["vcr_id"])
        if battle_key in seen:
            continue
        seen.add(battle_key)
        side_name = _side_for_ship(record["payload"], ship_id)
        if side_name is None:
            continue
        try:
            replay = replay_nuhost_from_nu_catalog(record["payload"], beams=beams, torpedoes=torpedoes, settings=settings)
        except ReplayUnsupported:
            continue
        return _state(replay, side_name, turn=record["turn"], vcr_id=record["vcr_id"], ship_id=ship_id)
    return None
