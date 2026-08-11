from pydantic import BaseModel


class AccountGameSummary(BaseModel):
    id: int
    name: str
    short_description: str

    status_id: int
    status_name: str

    turn: int
    slots: int

    next_host: str
    time_to_host: str

    is_private: bool
    is_custom: bool


class AccountGamesResponse(BaseModel):
    linked_account_id: int
    planets_username: str
    games: list[AccountGameSummary]
