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
    typical_open_utc_minute: number | null;
    typical_ready_utc_minute: number | null;
    median_open_after_host_minutes: number | null;
    median_ready_after_host_minutes: number | null;
    prediction_confidence: "none" | "low" | "medium" | "high";
}

export interface PlayerActivityResponse {
    game_id: number;
    through_turn: number | null;
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
