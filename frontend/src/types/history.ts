export interface HistoricalIntelAccountCoverage {
    linked_account_id: number;
    planets_username: string;
    is_owned: boolean;
    participates_in_game: boolean;
    turns: number[];
}

export interface HistoricalIntelStatus {
    game_id: number;
    current_turn: number;
    primary_linked_account_id: number;
    accounts: HistoricalIntelAccountCoverage[];
    available_turns: number[];
    complete_turns: number[];
}

export type HistoricalBackfillStatus =
    | "stored"
    | "cached"
    | "skipped"
    | "unavailable"
    | "failed";

export interface HistoricalBackfillAccountResult {
    linked_account_id: number;
    planets_username: string;
    status: HistoricalBackfillStatus;
    detail: string | null;
}

export interface HistoricalBackfillTurnResponse {
    game_id: number;
    turn: number;
    accounts: number;
    stored: number;
    cached: number;
    skipped: number;
    unavailable: number;
    failed: number;
    results: HistoricalBackfillAccountResult[];
}

export type HistoricalShipEvidence = "scan" | "combat";

export type HistoricalCombatOutcome =
    | "unknown"
    | "survived_to_later_combat"
    | "defeated";

export interface HistoricalCombatEventSide {
    side: "left" | "right";
    object_kind: "ship" | "planet";
    object_id: number | null;
    owner_id: number | null;
    name: string | null;
    hull_id: number | null;
    has_starbase: boolean | null;
    sequence_status: HistoricalCombatOutcome | null;
}

export interface HistoricalCombatEvent {
    vcr_id: number;
    turn: number;
    battle_type: number | null;
    x: number | null;
    y: number | null;
    sequence_index: number;
    sequence_count: number;
    analysis_basis: "later_vcr_same_turn_same_position";
    sides: [HistoricalCombatEventSide, HistoricalCombatEventSide];
}

export interface CombatEventSource {
    linked_account_id: number;
    planets_username: string;
    batch_ids: number[];
}

export type CombatEventResultStatus =
    | "unknown"
    | "survived_post_host"
    | "survived_to_later_combat"
    | "defeated"
    | "planet_held_post_host"
    | "planet_owner_changed_post_host";

export interface CombatEventSideSummary {
    side: "left" | "right";
    object_kind: "ship" | "planet";
    object_id: number | null;
    owner_id: number | null;
    name: string | null;
    hull_id: number | null;
    has_starbase: boolean | null;
    sequence_status: HistoricalCombatOutcome | null;
    result_status: CombatEventResultStatus;
    result_basis: string | null;
    result_sources: CombatEventSource[];
    post_host_owner_id: number | null;
}

export interface CombatEventSummary {
    vcr_id: number;
    turn: number;
    battle_type: number | null;
    x: number | null;
    y: number | null;
    sequence_index: number;
    sequence_count: number;
    sources: CombatEventSource[];
    sides: [CombatEventSideSummary, CombatEventSideSummary];
}

export interface CombatEventsResponse {
    game_id: number;
    turn: number;
    events: CombatEventSummary[];
}

export interface HistoricalShipTrackPoint {
    turn: number;
    snapshot_turn: number;
    x: number;
    y: number;
    linked_account_ids: number[];
    observer_names: string[];
    gap_from_previous: boolean;
    evidence: HistoricalShipEvidence;
    combat_vcr_id: number | null;
    combat_outcome: HistoricalCombatOutcome | null;
    combat_event: HistoricalCombatEvent | null;
    has_direct_scan: boolean;
}

export interface HistoricalShipTrack {
    ship_id: number;
    name: string | null;
    owner_id: number | null;
    hull_id: number | null;
    first_turn: number;
    last_turn: number;
    points: HistoricalShipTrackPoint[];
}

export interface HistoricalShipTracksResponse {
    game_id: number;
    through_turn: number;
    tracks: HistoricalShipTrack[];
}
