import asyncio
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.score_observation import ScoreObservation
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


SCORE_SOURCE = "planets.nu/loadscores"


def upsert_game(
    session: Session,
    raw: dict[str, Any],
) -> None:
    stmt = insert(Game).values(
        id=raw["id"],
        name=raw["name"],
        status_id=raw["status"],
        status_name=raw["statusname"],
        current_turn=raw["turn"],
        slots=raw["slots"],
        is_private=raw["isprivate"],
        is_custom=raw["iscustom"],
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=[Game.id],
        set_={
            "name": stmt.excluded.name,
            "status_id": stmt.excluded.status_id,
            "status_name": stmt.excluded.status_name,
            "current_turn": stmt.excluded.current_turn,
            "slots": stmt.excluded.slots,
            "is_private": stmt.excluded.is_private,
            "is_custom": stmt.excluded.is_custom,
            "updated_at": func.now(),
        },
    )

    session.execute(stmt)


def upsert_player_slots(
    session: Session,
    game_id: int,
    game_turn: int,
    players: list[dict[str, Any]],
) -> None:
    for raw in players:
        stmt = insert(GamePlayerSlot).values(
            game_id=game_id,
            slot_id=raw["id"],
            account_id=raw["accountid"],
            username=raw["username"],
            race_id=raw["raceid"],
            status=raw["status"],
            first_seen_turn=game_turn,
            last_seen_turn=game_turn,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                GamePlayerSlot.game_id,
                GamePlayerSlot.slot_id,
            ],
            set_={
                "account_id": stmt.excluded.account_id,
                "username": stmt.excluded.username,
                "race_id": stmt.excluded.race_id,
                "status": stmt.excluded.status,
                "last_seen_turn": stmt.excluded.last_seen_turn,
                "updated_at": func.now(),
            },
        )

        session.execute(stmt)


def make_score_row(
    game_id: int,
    raw: dict[str, Any],
) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "turn": raw["turn"],
        "slot_id": raw["ownerid"],
        "account_id": raw["accountid"],
        "source": SCORE_SOURCE,
        "source_date_added": raw.get("dateadded"),
        "capital_ships": raw["capitalships"],
        "freighters": raw["freighters"],
        "planets": raw["planets"],
        "starbases": raw["starbases"],
        "military_score": raw["militaryscore"],
        "inventory_score": raw["inventoryscore"],
        "priority_points": raw["prioritypoints"],
        "military_percent": Decimal(str(raw["percent"])),
        "victory_score": raw["victoryscore"],
        "victory_bonuses": raw.get("victorybonuses") or "",
        "technological_accumulator": raw[
            "technologicalaccumulator"
        ],
        "widest_reach": raw["widestreach"],
        "greatest_warrior": raw["greatestwarrior"],
        "happy_beings": raw["happybeings"],
    }


def insert_scores(
    session: Session,
    game_id: int,
    scores: list[dict[str, Any]],
) -> int:
    if not scores:
        return 0

    rows = [
        make_score_row(
            game_id,
            raw,
        )
        for raw in scores
    ]

    stmt = (
        insert(ScoreObservation)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_score_observation_source",
        )
        .returning(ScoreObservation.id)
    )

    result = session.execute(stmt)

    return len(result.scalars().all())


async def sync_public_game(
    game_id: int,
) -> dict[str, int]:
    client = PlanetsNuClient()

    load_info, scores = await asyncio.gather(
        client.load_info(game_id),
        client.load_scores(game_id),
    )

    game = load_info.get("game")
    players = load_info.get("players")

    if not isinstance(game, dict):
        raise PlanetsNuError(
            "loadinfo has no valid game object"
        )

    if game.get("id") != game_id:
        raise PlanetsNuError(
            "loadinfo returned a different game id"
        )

    if not isinstance(players, list):
        raise PlanetsNuError(
            "loadinfo has no valid players list"
        )

    if not all(isinstance(player, dict) for player in players):
        raise PlanetsNuError(
            "loadinfo players list contains invalid records"
        )

    with SessionLocal() as session:
        try:
            upsert_game(
                session,
                game,
            )

            upsert_player_slots(
                session,
                game_id=game_id,
                game_turn=game["turn"],
                players=players,
            )

            scores_inserted = insert_scores(
                session,
                game_id=game_id,
                scores=scores,
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    return {
        "game_id": game_id,
        "turn": game["turn"],
        "slots_seen": len(players),
        "scores_received": len(scores),
        "scores_inserted": scores_inserted,
    }
