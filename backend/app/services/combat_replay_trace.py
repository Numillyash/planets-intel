from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_trace import replay_nuhost_trace


def get_combat_replay_trace(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
) -> dict[str, Any] | None:
    accessible_ids = {
        account.id
        for account in accessible_intel_accounts(user_id=user_id)
    }
    if linked_account_id not in accessible_ids:
        return None

    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(
                GameRuleCatalog.game_id == game_id
            )
        ).scalar_one_or_none()
        if catalog is None:
            return None

        row = session.execute(
            select(CombatObservation, PrivateObservationBatch)
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
                CombatObservation.battle_turn == turn,
                CombatObservation.vcr_id == vcr_id,
            )
            .order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
            .limit(1)
        ).first()

        if row is None:
            return None

        combat, _batch = row
        payload = (
            dict(combat.payload)
            if isinstance(combat.payload, dict)
            else {}
        )

        try:
            trace = replay_nuhost_trace(
                payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported as exc:
            return {
                "game_id": game_id,
                "turn": turn,
                "vcr_id": vcr_id,
                "supported": False,
                "reason": str(exc),
                "frames": [],
            }

        return {
            **trace,
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "supported": True,
            "reason": None,
        }
