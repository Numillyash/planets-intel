from __future__ import annotations

from typing import Any


def replay_state_identity(*, turn: int, vcr_id: int, ship_id: int) -> dict[str, Any]:
    return {"turn": turn, "vcr_id": vcr_id, "ship_id": ship_id}
