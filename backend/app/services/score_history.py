from typing import Any

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.score_observation import ScoreObservation


SCORE_SOURCE = "planets.nu/loadscores"


def _delta(
    current: int,
    previous: int | None,
) -> int | None:
    if previous is None:
        return None

    return current - previous


def get_score_history(
    game_id: int,
    slot_id: int | None = None,
    from_turn: int | None = None,
    to_turn: int | None = None,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        game = session.get(
            Game,
            game_id,
        )

        if game is None:
            return None

        partition = {
            "partition_by": ScoreObservation.slot_id,
            "order_by": ScoreObservation.turn,
        }

        history_query = (
            select(
                ScoreObservation.turn.label("turn"),
                ScoreObservation.slot_id.label("slot_id"),
                ScoreObservation.account_id.label("account_id"),
                ScoreObservation.capital_ships.label(
                    "capital_ships"
                ),
                ScoreObservation.freighters.label(
                    "freighters"
                ),
                ScoreObservation.planets.label("planets"),
                ScoreObservation.starbases.label(
                    "starbases"
                ),
                ScoreObservation.military_score.label(
                    "military_score"
                ),
                ScoreObservation.inventory_score.label(
                    "inventory_score"
                ),
                ScoreObservation.priority_points.label(
                    "priority_points"
                ),
                ScoreObservation.military_percent.label(
                    "military_percent"
                ),
                ScoreObservation.victory_score.label(
                    "victory_score"
                ),
                ScoreObservation.source_date_added.label(
                    "source_date_added"
                ),
                ScoreObservation.observed_at.label(
                    "observed_at"
                ),
                func.lag(
                    ScoreObservation.turn
                ).over(**partition).label(
                    "previous_turn"
                ),
                func.lag(
                    ScoreObservation.capital_ships
                ).over(**partition).label(
                    "previous_capital_ships"
                ),
                func.lag(
                    ScoreObservation.freighters
                ).over(**partition).label(
                    "previous_freighters"
                ),
                func.lag(
                    ScoreObservation.planets
                ).over(**partition).label(
                    "previous_planets"
                ),
                func.lag(
                    ScoreObservation.starbases
                ).over(**partition).label(
                    "previous_starbases"
                ),
                func.lag(
                    ScoreObservation.military_score
                ).over(**partition).label(
                    "previous_military_score"
                ),
                func.lag(
                    ScoreObservation.inventory_score
                ).over(**partition).label(
                    "previous_inventory_score"
                ),
                func.lag(
                    ScoreObservation.priority_points
                ).over(**partition).label(
                    "previous_priority_points"
                ),
            )
            .where(
                ScoreObservation.game_id == game_id,
                ScoreObservation.source == SCORE_SOURCE,
            )
        )

        if slot_id is not None:
            history_query = history_query.where(
                ScoreObservation.slot_id == slot_id
            )

        history = history_query.subquery()

        query = select(history)

        if from_turn is not None:
            query = query.where(
                history.c.turn >= from_turn
            )

        if to_turn is not None:
            query = query.where(
                history.c.turn <= to_turn
            )

        query = query.order_by(
            history.c.turn,
            history.c.slot_id,
        )

        rows = session.execute(
            query
        ).mappings().all()

        items: list[dict[str, Any]] = []

        for row in rows:
            previous_turn = row["previous_turn"]

            turn_gap = (
                row["turn"] - previous_turn
                if previous_turn is not None
                else None
            )

            items.append(
                {
                    "turn": row["turn"],
                    "slot_id": row["slot_id"],
                    "account_id": row["account_id"],
                    "capital_ships": row[
                        "capital_ships"
                    ],
                    "freighters": row["freighters"],
                    "planets": row["planets"],
                    "starbases": row["starbases"],
                    "military_score": row[
                        "military_score"
                    ],
                    "inventory_score": row[
                        "inventory_score"
                    ],
                    "priority_points": row[
                        "priority_points"
                    ],
                    "military_percent": float(
                        row["military_percent"]
                    ),
                    "victory_score": row[
                        "victory_score"
                    ],
                    "previous_turn": previous_turn,
                    "turn_gap": turn_gap,
                    "delta_capital_ships": _delta(
                        row["capital_ships"],
                        row["previous_capital_ships"],
                    ),
                    "delta_freighters": _delta(
                        row["freighters"],
                        row["previous_freighters"],
                    ),
                    "delta_planets": _delta(
                        row["planets"],
                        row["previous_planets"],
                    ),
                    "delta_starbases": _delta(
                        row["starbases"],
                        row["previous_starbases"],
                    ),
                    "delta_military_score": _delta(
                        row["military_score"],
                        row["previous_military_score"],
                    ),
                    "delta_inventory_score": _delta(
                        row["inventory_score"],
                        row["previous_inventory_score"],
                    ),
                    "delta_priority_points": _delta(
                        row["priority_points"],
                        row["previous_priority_points"],
                    ),
                    "source_date_added": row[
                        "source_date_added"
                    ],
                    "observed_at": row["observed_at"],
                }
            )

        return {
            "game_id": game_id,
            "current_turn": game.current_turn,
            "source": SCORE_SOURCE,
            "slot_id": slot_id,
            "from_turn": from_turn,
            "to_turn": to_turn,
            "count": len(items),
            "items": items,
        }
