from pydantic import BaseModel


class AccountGameSummary(BaseModel):
    id: int
    name: str
    short_description: str

    status_id: int
    status_name: str

    turn: int
    slots: int
    turn_status: str | None = None

    next_host: str
    time_to_host: str

    is_private: bool
    is_custom: bool

    data_source: str = "planets.nu"

    # Local factual membership evidence. These fields remain optional because
    # a game returned only by upstream games/list may not have been observed or
    # canonically synced yet.
    observer_slot_id: int | None = None
    observer_status: int | None = None
    membership_source: str | None = None


class AccountGamesResponse(BaseModel):
    linked_account_id: int
    planets_username: str
    games: list[AccountGameSummary]
    upstream_available: bool = True
    upstream_error: str | None = None
