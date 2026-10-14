from typing import Literal

from pydantic import BaseModel


class CommanderHistoryGame(BaseModel):
    game_id: int
    name: str
    status_id: int
    status_name: str
    turn: int | None
    date_created: str | None
    date_ended: str | None


class CommanderSourceProvenance(BaseModel):
    source: str
    fetched_at: str | None
    cache_state: str
    warning: str | None = None


class CommanderHistoryProvenance(CommanderSourceProvenance):
    status_filter: list[int]


class ParticipationInterval(BaseModel):
    username: str
    game_id: int
    slot_id: int | None
    turn_from: int | None
    turn_to: int | None
    race_id: int | None
    race_name: str | None
    source: str
    source_event_ids: list[int]
    reconstruction_quality: str
    bounds_known: bool
    basis: str


class OverlapInterval(BaseModel):
    turn_from: int
    turn_to: int
    turn_count: int


class CommanderRaceHistoryItem(BaseModel):
    game_id: int
    game_name: str
    race_id: int | None
    race_name: str | None
    reconstruction_quality: str
    source: str


class CommanderRaceHistoryCoverage(BaseModel):
    games_with_attributable_race: int
    public_history_games: int | None
    complete: bool
    basis: str


class CommanderPeerSummary(BaseModel):
    username: str
    shared_games: int
    games_with_actual_turn_overlap: int | None
    overlapping_turn_count: int | None
    known_overlapping_turn_count: int
    overlap_reconstruction_complete: bool


class CommanderDossier(BaseModel):
    username: str
    username_normalized: str
    slot_id: int
    account_id: int | None
    race_id: int
    status: int
    source: str
    source_game_id: int
    source_turn: int

    history_status: Literal["available", "unavailable"]
    public_history_games: list[CommanderHistoryGame]
    public_history_game_count: int | None
    history_provenance: CommanderHistoryProvenance
    current_game_peer_history: list[CommanderPeerSummary]

    race_history: list[CommanderRaceHistoryItem]
    race_frequency: dict[str, int]
    race_history_coverage: CommanderRaceHistoryCoverage


class CommanderPairGame(BaseModel):
    game_id: int
    name: str
    status_id: int
    status_name: str
    turn: int | None
    date_created: str | None
    date_ended: str | None

    player_a_intervals: list[ParticipationInterval]
    player_b_intervals: list[ParticipationInterval]
    overlap_intervals: list[OverlapInterval]
    overlapping_turn_count: int | None
    overlap_status: str
    provenance: CommanderSourceProvenance


class CommanderPairSummary(BaseModel):
    player_a: str
    player_b: str
    shared_games: int | None
    games_with_actual_turn_overlap: int | None
    overlapping_turn_count: int | None
    known_overlapping_turn_count: int
    overlap_reconstruction_complete: bool
    first_shared_occurrence: CommanderHistoryGame | None
    last_shared_occurrence: CommanderHistoryGame | None
    games: list[CommanderPairGame]
    status: str


class CommanderIntelligenceProvenance(BaseModel):
    current_roster_source: str
    player_history_source: str
    participation_source: str
    public_history_status_filter: list[int]
    facts_unchanged: bool


class CommanderIntelligenceResponse(BaseModel):
    game_id: int
    game_name: str
    turn: int
    status_id: int
    status_name: str

    analysis_kind: Literal["derived_historical_summary"]
    method_version: str
    behavioral_inference: Literal[False]

    commanders: list[CommanderDossier]
    pairwise: list[CommanderPairSummary]
    provenance: CommanderIntelligenceProvenance
    warnings: list[str]
