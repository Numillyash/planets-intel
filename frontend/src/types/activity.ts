export interface PlayerActivityItem {
    slot_id: number;
    username: string;
    race_id: number;
    current_turn: number | null;
    current_state: "unopened" | "open" | "ready" | "ready_marker" | "dead" | "computer" | "unknown";
    state_observed_at: string | null;
    first_open_observed_at: string | null;
    ready_at: string | null;
    open_samples: number;
    ready_samples: number;
    open_utc_minutes: number[];
    ready_utc_minutes: number[];
    typical_open_utc_minute: number | null;
    typical_ready_utc_minute: number | null;
    median_open_after_host_minutes: number | null;
    median_ready_after_host_minutes: number | null;
    prediction_confidence: "none" | "low" | "medium" | "high";
    all_current_games_count: number;
    all_current_games_open_samples: number;
    all_current_games_ready_samples: number;
    all_current_games_open_utc_minutes: number[];
    all_current_games_ready_utc_minutes: number[];
    all_current_games_prediction_confidence: "none" | "low" | "medium" | "high";
}

export interface PlayerActivityResponse {
    game_id: number;
    through_turn: number | null;
    current_games_considered: number;
    polling_note: string;
    players: PlayerActivityItem[];
}

export interface HostEventSource {
    linked_account_id: number;
    planets_username: string;
    batch_id: number;
}

export interface HostEventItem {
    event_type: string;
    turn: number;
    planet_id: number | null;
    starbase_id: number | null;
    ship_id: number | null;
    ship_name: string | null;
    x: number | null;
    y: number | null;
    summary: string;
    sources: HostEventSource[];
}

export interface HostEventsResponse {
    game_id: number;
    turn: number;
    count: number;
    events: HostEventItem[];
}

export type GameActivityKind =
    | "system"
    | "diplomacy"
    | "private_message"
    | "player_message"
    | "unclassified";

export type GameActivityVisibilitySource =
    | "ingame_activity"
    | "private_activity"
    | "outgoing_private_write";

export interface GameActivityItem {
    activity_id: number;
    activity_type: number | null;
    scope: number | null;
    visibility_source?: GameActivityVisibilitySource | null;
    outgoing_recipient_player_ids?: number[] | null;
    turn: number | null;
    parent_id: number | null;
    source_id: number | null;
    source_name: string | null;
    source_type: number | null;
    target_id: number | null;
    target_name: string | null;
    target_type: number | null;
    message: string | null;
    date_added: string | null;
    kind: GameActivityKind;
    thread_root_id: number | null;
    conversation_with_id: number | null;
    conversation_with_name: string | null;
    conversation_player_ids: number[];
}

export interface GameActivityResponse {
    game_id: number;
    linked_account_id: number;
    count: number;
    items: GameActivityItem[];
}

export interface SendGameMessageResponse {
    game_id: number;
    linked_account_id: number;
    sender_player_id: number;
    recipient_player_ids: number[];
    upstream_accepted: boolean;
    reconciled: boolean;
    upstream_html: string | null;
    reconciliation_detail: string | null;
}
