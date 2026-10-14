from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from app.services.movement_intercept import Point


class MovementPhase(StrEnum):
    FACTUAL = "factual"
    TOW = "tow"
    MOVE_MOST = "move_most"
    INTERCEPT = "intercept"


@dataclass(frozen=True, slots=True)
class MovementPositionState:
    """Request-local knowledge about one ship after a movement phase.

    A missing/unsupported Host substep is represented explicitly by
    ``position=None`` rather than by silently falling back to the factual start
    position. This keeps later movement phases from consuming a plausible but
    unsupported endpoint.
    """

    ship_id: int
    position: Point | None
    phase: MovementPhase
    certain: bool
    reason: str


@dataclass(slots=True)
class MovementTurnState:
    """Request-local position ledger shared by ordered movement phases."""

    positions: dict[int, MovementPositionState] = field(default_factory=dict)

    def set_known(
        self,
        ship_id: int,
        position: Point,
        *,
        phase: MovementPhase,
        reason: str,
    ) -> MovementPositionState:
        state = MovementPositionState(
            ship_id=int(ship_id),
            position=position,
            phase=phase,
            certain=True,
            reason=reason,
        )
        self.positions[int(ship_id)] = state
        return state

    def set_unresolved(
        self,
        ship_id: int,
        *,
        phase: MovementPhase,
        reason: str,
    ) -> MovementPositionState:
        state = MovementPositionState(
            ship_id=int(ship_id),
            position=None,
            phase=phase,
            certain=False,
            reason=reason,
        )
        self.positions[int(ship_id)] = state
        return state

    def merge_known(
        self,
        positions: Mapping[int, Point],
        *,
        phase: MovementPhase,
        reason: str,
    ) -> None:
        for ship_id, position in positions.items():
            self.set_known(
                int(ship_id),
                position,
                phase=phase,
                reason=reason,
            )

    def get(self, ship_id: int) -> MovementPositionState | None:
        return self.positions.get(int(ship_id))

    def known_positions(self) -> dict[int, Point]:
        return {
            ship_id: state.position
            for ship_id, state in self.positions.items()
            if state.certain and state.position is not None
        }

    def unresolved_ship_ids(self) -> frozenset[int]:
        return frozenset(
            ship_id
            for ship_id, state in self.positions.items()
            if not state.certain or state.position is None
        )
