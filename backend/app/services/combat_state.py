from typing import Any


from app.models.combat_state_observation import CombatStateObservation


def _vcr_contains_ship(payload: dict[str, Any], ship_id: int) -> bool:
    for side_name in ("left", "right"):
        side = payload.get(side_name)
        if (
            isinstance(side, dict)
            and side.get("objectid") == ship_id
            and side.get("hullid") not in (None, 0)
        ):
            return True
    return False


def upsert_combat_state(
    *,
    user_id: int,
    game_id: int,
    turn: int,
    vcr_id: int,
    ship_id: int,
    post_combat_torpedoes: int | None,
    post_combat_fighters: int | None,
    note: str | None,
) -> dict[str, Any] | None:
    """P0: legacy analyst rows have no selected observer provenance.

    Do not write cross-observer annotations until a provenance-bearing
    schema and authorization model are reviewed.
    """
    return None


def combat_state_map(
    *,
    user_id: int,
    game_id: int,
    turn: int,
) -> dict[tuple[int, int], CombatStateObservation]:
    """Quarantine old analyst annotations that may originate from peers."""
    return {}


def latest_ship_combat_state(
    *,
    user_id: int,
    game_id: int,
    ship_id: int,
    through_turn: int,
) -> CombatStateObservation | None:
    """Quarantine old analyst annotations on threat/replay read paths."""
    return None
