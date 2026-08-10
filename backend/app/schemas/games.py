from pydantic import BaseModel


class GameInfo(BaseModel):
    id: int
    name: str
    description: str
    short_description: str
    status_id: int
    status_name: str
    slots: int
    next_host: str
    turns_per_week: int
    is_private: bool
    is_custom: bool
    win_condition_id: int


class GameSettingsInfo(BaseModel):

    map_width: int
    map_height: int
    map_shape: int
    num_planets: int
    ship_limit: int

    planet_scan_range: int
    ship_scan_range: int

    max_allies: int
    max_share_intel: int
    max_safe_passage: int

    all_visible: bool
    all_planets_visible: bool
    planet_ownership_visible: bool
    starbases_visible: bool
    ships_at_planets_visible: bool
    minefields_visible: bool
    all_wormholes_visible: bool

    unlimited_fuel: bool
    unlimited_ammo: bool
    no_supplies: bool

    military_score_percent: int

    production_queue: bool
    planetary_production_queue: bool

    fight_or_fail: int
    fof_active_turn: int
    fof_increment: int

    nebulas: int
    stars: int
    max_wormholes: int
    wormhole_scan_range: int


class PlayerInfo(BaseModel):
    slot_id: int
    account_id: int
    username: str
    race_id: int

    status: int
    turn_status: int

    planets: int
    ships: int
    starbases: int

    turn_ready: bool


class RelationInfo(BaseModel):
    id: int

    player_id: int
    player_to_id: int

    relation_to: int
    relation_from: int
    conflict_level: int

    color: str


class GameDetailsResponse(BaseModel):
    source: str = "planets.nu/loadinfo"

    game: GameInfo
    settings: GameSettingsInfo

    players: list[PlayerInfo]
    relations: list[RelationInfo]

    schedule: str
    time_to_host: str
    year_from: str
    year_to: str
    win_condition: str
