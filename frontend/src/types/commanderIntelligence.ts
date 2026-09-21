export interface CommanderHistoryGame {
    game_id: number;
    name: string;
    status_id: number;
    status_name: string;
    turn: number | null;
    date_created: string | null;
    date_ended: string | null;
}

export interface CommanderSourceProvenance {
    source: string;
    fetched_at: string | null;
    cache_state: string;
    warning?: string | null;
}

export interface CommanderHistoryProvenance extends CommanderSourceProvenance {
    status_filter: number[];
}

export interface CommanderParticipationInterval {
    username: string;
    game_id: number;
    slot_id: number | null;
    turn_from: number | null;
    turn_to: number | null;
    race_id: number | null;
    race_name: string | null;
    source: string;
    source_event_ids: number[];
    reconstruction_quality: string;
    bounds_known: boolean;
    basis: string;
}

export interface CommanderOverlapInterval {
    turn_from: number;
    turn_to: number;
    turn_count: number;
}

export interface CommanderRaceHistoryItem {
    game_id: number;
    game_name: string;
    race_id: number | null;
    race_name: string | null;
    reconstruction_quality: string;
    source: string;
}

export interface CommanderPeerSummary {
    username: string;
    shared_games: number;
    games_with_actual_turn_overlap: number | null;
    overlapping_turn_count: number | null;
    known_overlapping_turn_count: number;
    overlap_reconstruction_complete: boolean;
}

export interface CommanderDossier {
    username: string;
    username_normalized: string;
    slot_id: number;
    account_id: number | null;
    race_id: number;
    status: number;
    source: string;
    source_game_id: number;
    source_turn: number;

    history_status: "available" | "unavailable";
    public_history_games: CommanderHistoryGame[];
    public_history_game_count: number | null;
    history_provenance: CommanderHistoryProvenance;
    prior_current_game_peers: CommanderPeerSummary[];

    race_history: CommanderRaceHistoryItem[];
    race_frequency: Record<string, number>;
    race_history_coverage: {
        games_with_attributable_race: number;
        public_history_games: number | null;
        complete: boolean;
        basis: string;
    };
}

export interface CommanderPairGame extends CommanderHistoryGame {
    player_a_intervals: CommanderParticipationInterval[];
    player_b_intervals: CommanderParticipationInterval[];
    overlap_intervals: CommanderOverlapInterval[];
    overlapping_turn_count: number | null;
    overlap_status: string;
    provenance: CommanderSourceProvenance;
}

export interface CommanderPairSummary {
    player_a: string;
    player_b: string;
    shared_games: number | null;
    games_with_actual_turn_overlap: number | null;
    overlapping_turn_count: number | null;
    known_overlapping_turn_count: number;
    overlap_reconstruction_complete: boolean;
    first_shared_occurrence: CommanderHistoryGame | null;
    last_shared_occurrence: CommanderHistoryGame | null;
    games: CommanderPairGame[];
    status: string;
}

export interface CommanderIntelligenceResponse {
    game_id: number;
    game_name: string;
    turn: number;
    status_id: number;
    status_name: string;
    analysis_kind: "derived_historical_summary";
    method_version: string;
    behavioral_inference: false;
    commanders: CommanderDossier[];
    pairwise: CommanderPairSummary[];
    provenance: {
        current_roster_source: string;
        player_history_source: string;
        participation_source: string;
        public_history_status_filter: number[];
        facts_unchanged: boolean;
    };
    warnings: string[];
}
