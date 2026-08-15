from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.player_turn_activity_observation import (
    PlayerTurnActivityObservation,
)
from app.models.score_observation import ScoreObservation


def _latest_scores(
    game_id: int,
    current_turn: int,
) -> dict[int, ScoreObservation]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ScoreObservation)
            .where(
                ScoreObservation.game_id == game_id,
                ScoreObservation.turn <= current_turn,
            )
            .order_by(
                ScoreObservation.turn.desc(),
                ScoreObservation.observed_at.desc(),
                ScoreObservation.id.desc(),
            )
        ).scalars().all()

    result: dict[int, ScoreObservation] = {}
    for row in rows:
        result.setdefault(row.slot_id, row)
    return result


def _latest_activity(
    game_id: int,
    current_turn: int,
) -> dict[int, PlayerTurnActivityObservation]:
    with SessionLocal() as session:
        rows = session.execute(
            select(PlayerTurnActivityObservation)
            .where(
                PlayerTurnActivityObservation.game_id == game_id,
                PlayerTurnActivityObservation.turn <= current_turn,
            )
            .order_by(
                PlayerTurnActivityObservation.turn.desc(),
                PlayerTurnActivityObservation.observed_at.desc(),
                PlayerTurnActivityObservation.id.desc(),
            )
        ).scalars().all()

    result: dict[int, PlayerTurnActivityObservation] = {}
    for row in rows:
        result.setdefault(row.slot_id, row)
    return result


def get_cached_game_details_payload(
    game_id: int,
) -> dict[str, Any] | None:
    """Build a conservative loadinfo-shaped view from canonical storage.

    This is an availability fallback only. Fields that are not persisted as
    canonical facts (relations, schedule, next-host text, descriptions) are
    deliberately left empty instead of being invented.
    """
    with SessionLocal() as session:
        game = session.get(Game, game_id)
        catalog = session.get(GameRuleCatalog, game_id)

        if game is None or catalog is None:
            return None

        slots = session.execute(
            select(GamePlayerSlot)
            .where(GamePlayerSlot.game_id == game_id)
            .order_by(GamePlayerSlot.slot_id)
        ).scalars().all()

        game_values = {
            "id": game.id,
            "name": game.name,
            "status": game.status_id,
            "statusname": game.status_name,
            "turn": game.current_turn,
            "slots": game.slots,
            "isprivate": game.is_private,
            "iscustom": game.is_custom,
        }
        settings = dict(catalog.settings or {})
        current_turn = game.current_turn

    # Some older persisted catalogs did not redundantly store the current
    # turn inside settings. It is canonical in games.current_turn.
    settings.setdefault("turn", current_turn)

    scores = _latest_scores(game_id, current_turn)
    activities = _latest_activity(game_id, current_turn)

    players: list[dict[str, Any]] = []
    for slot in slots:
        score = scores.get(slot.slot_id)
        activity = activities.get(slot.slot_id)

        # Public score rows normally cover every slot. If one is absent, keep
        # the game usable but mark counts with conservative zero placeholders;
        # callers can distinguish the whole response by source=canonical-cache.
        planets = score.planets if score is not None else 0
        ships = (
            score.capital_ships + score.freighters
            if score is not None
            else 0
        )
        starbases = score.starbases if score is not None else 0

        players.append(
            {
                "id": slot.slot_id,
                "accountid": slot.account_id or 0,
                "username": slot.username,
                "raceid": slot.race_id,
                "status": slot.status,
                "turnstatus": 0,
                "planets": planets,
                "ships": ships,
                "starbases": starbases,
                "turnready": (
                    activity.turn_ready
                    if activity is not None
                    else False
                ),
                "activeadvantages": "",
                "activehulls": "",
            }
        )

    return {
        "source": "canonical-cache",
        "game": {
            **game_values,
            "description": "",
            "shortdescription": "",
            "nexthost": "",
            "turnsperweek": 0,
            "wincondition": 0,
        },
        "settings": settings,
        "players": players,
        "relations": [],
        "schedule": "",
        "timetohost": "",
        "yearfrom": "",
        "yearto": "",
        "wincondition": "",
    }
