from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog


def get_game_rule_catalog_view(*, game_id: int) -> dict[str, Any] | None:
    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(
                GameRuleCatalog.game_id == game_id
            )
        ).scalar_one_or_none()

        if catalog is None:
            return None

        return {
            "game_id": int(catalog.game_id),
            "observed_turn": int(catalog.observed_turn),
            "settings": dict(catalog.settings),
            "races": list(catalog.races),
            "advantages": list(catalog.advantages),
            "hulls": list(catalog.hulls),
        }
