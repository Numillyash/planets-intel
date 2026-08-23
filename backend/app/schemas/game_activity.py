from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


class SendGameMessageRequest(BaseModel):
    linked_account_id: int = Field(gt=0)
    # Planets.nu uses an empty `to` field for a public/general message.  Keep
    # zero recipients as an explicit supported state instead of conflating it
    # with invalid input.  Non-empty lists still mean private recipients.
    recipient_player_ids: list[int] = Field(default_factory=list, max_length=31)
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("recipient_player_ids")
    @classmethod
    def validate_recipients(cls, value: list[int]) -> list[int]:
        if any(isinstance(item, bool) or item <= 0 for item in value):
            raise ValueError("recipient player ids must be positive integers")
        return list(dict.fromkeys(value))

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message body must not be blank")
        return value


class SendGameMessageResponse(BaseModel):
    game_id: int
    linked_account_id: int
    sender_player_id: int
    recipient_player_ids: list[int]
    upstream_accepted: bool
    reconciled: bool
    upstream_html: str | None = None
    reconciliation_detail: str | None = None
