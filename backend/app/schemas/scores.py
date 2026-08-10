from datetime import datetime

from pydantic import BaseModel


class ScoreHistoryItem(BaseModel):
    turn: int
    slot_id: int
    account_id: int | None

    capital_ships: int
    freighters: int
    planets: int
    starbases: int

    military_score: int
    inventory_score: int
    priority_points: int
    military_percent: float

    victory_score: int

    previous_turn: int | None
    turn_gap: int | None

    delta_capital_ships: int | None
    delta_freighters: int | None
    delta_planets: int | None
    delta_starbases: int | None
    delta_military_score: int | None
    delta_inventory_score: int | None
    delta_priority_points: int | None

    source_date_added: str | None
    observed_at: datetime


class ScoreHistoryResponse(BaseModel):
    game_id: int
    current_turn: int
    source: str

    slot_id: int | None
    from_turn: int | None
    to_turn: int | None

    count: int
    items: list[ScoreHistoryItem]
