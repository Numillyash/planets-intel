from typing import Any

from app.services.combat_replay_state import latest_ship_replay_state
from app.services.combat_state import latest_ship_combat_state
from app.services.threat_analysis import get_ship_threat_analysis


def _analyst_payload(state: Any) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "turn": state.turn,
        "vcr_id": state.vcr_id,
        "post_combat_torpedoes": state.post_combat_torpedoes,
        "post_combat_fighters": state.post_combat_fighters,
        "source": "analyst_confirmed_vcr_review",
    }


def _state_key(state: dict[str, Any] | None) -> tuple[int, int]:
    if state is None:
        return (-1, -1)
    return (int(state.get("turn") or -1), int(state.get("vcr_id") or -1))


def get_ship_threat_analysis_with_post_state(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    result = get_ship_threat_analysis(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        ship_id=ship_id,
    )
    if result is None or result.get("status") != "ok":
        return result

    analyst_row = latest_ship_combat_state(
        user_id=user_id,
        game_id=game_id,
        ship_id=ship_id,
        through_turn=turn,
    )
    analyst = _analyst_payload(analyst_row)
    replay = latest_ship_replay_state(
        user_id=user_id,
        game_id=game_id,
        ship_id=ship_id,
        through_turn=turn,
    )

    # Newer combat evidence wins. For the same VCR, explicit analyst review
    # takes precedence while deterministic replay remains visible as a check.
    if analyst is not None and _state_key(analyst) >= _state_key(replay):
        effective = analyst
    else:
        effective = replay

    same_event = (
        analyst is not None
        and replay is not None
        and _state_key(analyst) == _state_key(replay)
    )
    replay_matches_analyst = (
        same_event
        and (
            analyst.get("post_combat_torpedoes") is None
            or analyst.get("post_combat_torpedoes") == replay.get("post_combat_torpedoes")
        )
        and (
            analyst.get("post_combat_fighters") is None
            or analyst.get("post_combat_fighters") == replay.get("post_combat_fighters")
        )
    )

    loadout = result.get("loadout")
    if isinstance(loadout, dict):
        vcr = loadout.get("vcr_reveal")
        if isinstance(vcr, dict):
            vcr["combat_start_torpedoes"] = vcr.get("torpedoes")
            vcr["combat_start_fighters"] = vcr.get("fighters")
            vcr["replay_post_combat_torpedoes"] = (
                replay.get("post_combat_torpedoes") if replay is not None else None
            )
            vcr["replay_post_combat_fighters"] = (
                replay.get("post_combat_fighters") if replay is not None else None
            )
            vcr["replay_post_combat_shield"] = (
                replay.get("post_combat_shield") if replay is not None else None
            )
            vcr["replay_post_combat_damage"] = (
                replay.get("post_combat_damage") if replay is not None else None
            )
            vcr["replay_post_combat_crew"] = (
                replay.get("post_combat_crew") if replay is not None else None
            )
            vcr["replay_engine"] = replay.get("engine") if replay is not None else None
            vcr["replay_matches_analyst"] = replay_matches_analyst if same_event else None
            vcr["post_combat_torpedoes"] = (
                effective.get("post_combat_torpedoes") if effective is not None else None
            )
            vcr["post_combat_fighters"] = (
                effective.get("post_combat_fighters") if effective is not None else None
            )
            vcr["post_combat_turn"] = effective.get("turn") if effective is not None else None
            vcr["post_combat_vcr_id"] = effective.get("vcr_id") if effective is not None else None
            vcr["post_combat_source"] = effective.get("source") if effective is not None else None

    result["current_combat_state"] = effective
    result["replay_combat_state"] = replay
    result["analyst_combat_state"] = analyst
    result["replay_matches_analyst"] = replay_matches_analyst if same_event else None

    defense = result.get("defense")
    reasons = defense.get("reasons") if isinstance(defense, dict) else None
    if isinstance(reasons, list):
        if effective is not None and effective.get("post_combat_torpedoes") == 0:
            if effective.get("source") == "deterministic_vcr_replay":
                reasons.append(
                    "Deterministic NuHost replay derives 0 torpedoes after the latest observed combat; "
                    "tubes remain empty unless the ship rearms afterwards."
                )
            else:
                reasons.append(
                    "Latest analyst-confirmed post-combat torpedo ammo is 0; "
                    "tubes remain empty unless the ship rearms afterwards."
                )
        if replay_matches_analyst and replay is not None:
            reasons.append(
                f"Deterministic NuHost replay independently matches the analyst-confirmed "
                f"post-combat ammo for VCR #{replay['vcr_id']}."
            )

    return result
