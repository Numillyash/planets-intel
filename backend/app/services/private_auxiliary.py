from typing import Any

from sqlalchemy.orm import Session

from app.services.host_events import persist_safe_host_events
from app.services.player_activity import persist_private_ready_activity


def _dict_list(rst: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = rst.get(name)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def persist_private_auxiliary_observations(
    session: Session,
    *,
    game_id: int,
    turn: int,
    batch_id: int,
    rst: dict[str, Any],
) -> dict[str, int]:
    planets = _dict_list(rst, "planets")
    starbases = _dict_list(rst, "starbases")
    messages = _dict_list(rst, "messages")
    mymessages = _dict_list(rst, "mymessages")
    players = _dict_list(rst, "players")

    host_events = persist_safe_host_events(
        session,
        batch_id=batch_id,
        turn=turn,
        messages=messages,
        mymessages=mymessages,
        planets=planets,
        starbases=starbases,
    )
    ready_events = persist_private_ready_activity(
        session,
        game_id=game_id,
        turn=turn,
        players=players,
    )

    return {
        "host_events_inserted": host_events,
        "player_ready_observations_inserted": ready_events,
    }
