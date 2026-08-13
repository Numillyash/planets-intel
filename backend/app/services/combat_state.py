from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.combat_state_observation import CombatStateObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts


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
    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if not accessible_ids:
        return None

    with SessionLocal() as session:
        combats = list(
            session.execute(
                select(CombatObservation)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == CombatObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    CombatObservation.battle_turn == turn,
                    CombatObservation.vcr_id == vcr_id,
                )
            ).scalars().all()
        )
        if not any(
            isinstance(combat.payload, dict)
            and _vcr_contains_ship(combat.payload, ship_id)
            for combat in combats
        ):
            return None

        table = CombatStateObservation.__table__
        stmt = pg_insert(table).values(
            user_id=user_id,
            game_id=game_id,
            turn=turn,
            vcr_id=vcr_id,
            ship_id=ship_id,
            post_combat_torpedoes=post_combat_torpedoes,
            post_combat_fighters=post_combat_fighters,
            note=note.strip() if isinstance(note, str) and note.strip() else None,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_combat_state_observation_identity",
            set_={
                "post_combat_torpedoes": stmt.excluded.post_combat_torpedoes,
                "post_combat_fighters": stmt.excluded.post_combat_fighters,
                "note": stmt.excluded.note,
                "updated_at": func.now(),
            },
        ).returning(table)
        row = session.execute(stmt).mappings().one()
        session.commit()

    return {
        "game_id": row["game_id"],
        "turn": row["turn"],
        "vcr_id": row["vcr_id"],
        "ship_id": row["ship_id"],
        "post_combat_torpedoes": row["post_combat_torpedoes"],
        "post_combat_fighters": row["post_combat_fighters"],
        "note": row["note"],
        "source": "analyst_confirmed_vcr_review",
    }


def combat_state_map(
    *,
    user_id: int,
    game_id: int,
    turn: int,
) -> dict[tuple[int, int], CombatStateObservation]:
    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(CombatStateObservation).where(
                    CombatStateObservation.user_id == user_id,
                    CombatStateObservation.game_id == game_id,
                    CombatStateObservation.turn == turn,
                )
            ).scalars().all()
        )
    return {(row.vcr_id, row.ship_id): row for row in rows}


def latest_ship_combat_state(
    *,
    user_id: int,
    game_id: int,
    ship_id: int,
    through_turn: int,
) -> CombatStateObservation | None:
    with SessionLocal() as session:
        return session.execute(
            select(CombatStateObservation)
            .where(
                CombatStateObservation.user_id == user_id,
                CombatStateObservation.game_id == game_id,
                CombatStateObservation.ship_id == ship_id,
                CombatStateObservation.turn <= through_turn,
            )
            .order_by(
                CombatStateObservation.turn.desc(),
                CombatStateObservation.vcr_id.desc(),
                CombatStateObservation.updated_at.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
