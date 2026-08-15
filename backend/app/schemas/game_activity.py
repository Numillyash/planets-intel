from typing import Literal

from pydantic import BaseModel, Field


ActivityKind = Literal[
    "system",
    "diplomacy",
    "private_message",
    "player_message",
    "unclassified",
]


class GameActivityItemResponse(BaseModel):
    activity_id: int
    activity_type: int | None
    scope: int | None
    turn: int | None
    parent_id: int | None
    source_id: int | None
    source_name: str | None
    source_type: int | None
    target_id: int | None
    target_name: str | None
    target_type: int | None
    message: str | None
    date_added: str | None
    kind: ActivityKind
    thread_root_id: int | None = None
    conversation_with_id: int | None = None
    conversation_with_name: str | None = None


class GameActivityResponse(BaseModel):
    game_id: int
    linked_account_id: int
    count: int = Field(ge=0)
    items: list[GameActivityItemResponse]
