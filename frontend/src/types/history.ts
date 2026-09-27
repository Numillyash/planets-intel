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
    /**
     * Frontend-normalized alias of sequence_status used by map event UI.
     * It remains derived from stored factual VCR order, not a stored fact.
     */
    combat_outcome: HistoricalCombatOutcome | null;
    /**
     * True only for the tracked ship when its enclosing historical track point
     * has later structured host evidence confirming survival at the position.
     */
    post_host_confirmed: boolean;
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

export interface CombatEquipmentEvidence {
    beam_id: number | null;
    beam_count: number | null;
    launcher_count: number | null;
    bay_count: number | null;
    torpedo_id: number | null;
    torpedoes: number | null;
    fighters: number | null;
    shield: number | null;
    damage: number | null;
    crew: number | null;
    mass: number | null;
    race_id: number | null;
    evidence_basis: "vcr_combat_observation" | string;
    combat_start_torpedoes?: number | null;
    combat_start_fighters?: number | null;
    replay_post_combat_torpedoes?: number | null;
    replay_post_combat_fighters?: number | null;
    replay_post_combat_shield?: number | null;
    replay_post_combat_damage?: number | null;
    replay_post_combat_crew?: number | null;
    replay_survived?: boolean | null;
    replay_destroyed?: boolean | null;
    replay_captured?: boolean | null;
    replay_cycles?: number | null;
    replay_engine?: string | null;
    replay_basis?: string | null;
    post_combat_torpedoes?: number | null;
    post_combat_fighters?: number | null;
    post_combat_source?: string | null;
    replay_matches_analyst?: boolean | null;
}

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
    combat_equipment?: CombatEquipmentEvidence | null;
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
    post_host_confirmed: boolean;
    post_host_planet_id: number | null;
    post_host_basis: string | null;
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


export interface SpatialMessageItem {
    message_key: string;
    message_id: number | null;
    message_type: number | null;
    message_turn: number | null;
    owner_id: number | null;
    target_id: number | null;
    headline: string | null;
    body: string | null;
    x: number;
    y: number;
    source_collections: string[];
    batch_id: number;
    observed_at: string;
}

export interface SpatialMessagesResponse {
    game_id: number;
    turn: number;
    linked_account_id: number;
    planets_username: string;
    scope: "selected_observer_private_messages";
    count: number;
    messages: SpatialMessageItem[];
}
