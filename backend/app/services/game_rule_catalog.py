from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.game_rule_catalog import GameRuleCatalog


SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "email",
        "gamepassword",
        "password",
        "savekey",
    }
)

RULE_COLLECTIONS = (
    "hulls",
    "beams",
    "torpedos",
    "engines",
    "races",
    "advantages",
)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _safe_rule_list(rst: dict[str, Any], name: str) -> list[dict[str, Any]]:
    raw = rst.get(name)
    if not isinstance(raw, list):
        return []

    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sanitized = _sanitize(item)
        if isinstance(sanitized, dict):
            result.append(sanitized)

    result.sort(
        key=lambda item: (
            item.get("id") if isinstance(item.get("id"), int) else 10**9,
            str(item.get("name", "")),
        )
    )
    return result


def persist_game_rule_catalog(
    session: Session,
    *,
    game_id: int,
    turn: int,
    rst: dict[str, Any],
) -> None:
    settings_raw = rst.get("settings")
    settings = _sanitize(settings_raw) if isinstance(settings_raw, dict) else {}
    if not isinstance(settings, dict):
        settings = {}

    values: dict[str, Any] = {
        "game_id": game_id,
        "observed_turn": turn,
        "settings": settings,
    }
    for name in RULE_COLLECTIONS:
        values[name] = _safe_rule_list(rst, name)

    table = GameRuleCatalog.__table__
    stmt = pg_insert(table).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.game_id],
        set_={
            "observed_turn": stmt.excluded.observed_turn,
            "settings": stmt.excluded.settings,
            "hulls": stmt.excluded.hulls,
            "beams": stmt.excluded.beams,
            "torpedos": stmt.excluded.torpedos,
            "engines": stmt.excluded.engines,
            "races": stmt.excluded.races,
            "advantages": stmt.excluded.advantages,
        },
    )
    session.execute(stmt)
