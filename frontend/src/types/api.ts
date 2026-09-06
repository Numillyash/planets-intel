export interface GameInfo {
    id: number;
    name: string;
    description: string;
    short_description: string;
    status_id: number;
    status_name: string;
    turn: number;
    slots: number;
    turn_status: string | null;
    next_host: string;
    turns_per_week: number | null;
    is_private: boolean;
    is_custom: boolean;
    win_condition_id: number | null;
}

export interface GameSettings {
    turn: number;
    map_width: number;
    map_height: number;
    map_shape: number;
    num_planets: number;
    ship_limit: number;
    planet_scan_range: number;
    ship_scan_range: number;
    max_allies: number;
    max_share_intel: number;
    max_safe_passage: number;
    all_visible: boolean;
    all_planets_visible: boolean;
    planet_ownership_visible: boolean;
    starbases_visible: boolean;
    ships_at_planets_visible: boolean;
    minefields_visible: boolean;
    all_wormholes_visible: boolean;
    unlimited_fuel: boolean;
    unlimited_ammo: boolean;
    no_supplies: boolean;
    military_score_percent: number;
    production_queue: boolean;
    planetary_production_queue: boolean;
    fight_or_fail: number;
    fof_active_turn: number;
    fof_increment: number;
    nebulas: number;
    stars: number;
    max_wormholes: number;
    wormhole_scan_range: number;
}

export interface PlayerInfo {
    slot_id: number;
    account_id: number | null;
    username: string;
    race_id: number;
    status: number;
    turn_status: number | null;
    turns_missed: number | null;
    planets: number | null;
    ships: number | null;
    starbases: number | null;
    turn_ready: boolean | null;
    active_advantages: string;
    active_hulls: string;
}

export interface RelationInfo {
    id: number;
    player_id: number;
    player_to_id: number;
    relation_to: number;
    relation_from: number;
    conflict_level: number;
    color: string;
}

export interface GameDetailsResponse {
    source: string;
    game: GameInfo;
    settings: GameSettings;
    players: PlayerInfo[];
    relations: RelationInfo[];
    schedule: string;
    time_to_host: string;
    year_from: string;
    year_to: string;
    win_condition: string;
}

export interface ScoreHistoryItem {
    turn: number;
    slot_id: number;
    account_id: number | null;
    capital_ships: number;
    freighters: number;
    planets: number;
    starbases: number;
    military_score: number;
    inventory_score: number;
    priority_points: number;
    military_percent: number;
    victory_score: number;
    previous_turn: number | null;
    turn_gap: number | null;
    delta_capital_ships: number | null;
    delta_freighters: number | null;
    delta_planets: number | null;
    delta_starbases: number | null;
    delta_military_score: number | null;
    delta_inventory_score: number | null;
    delta_priority_points: number | null;
    source_date_added: string | null;
    observed_at: string;
}

export interface ScoreHistoryResponse {
    game_id: number;
    current_turn: number;
    source: string;
    slot_id: number | null;
    from_turn: number | null;
    to_turn: number | null;
    count: number;
    items: ScoreHistoryItem[];
}

export interface CurrentUserResponse {
    id: number;
    username: string;
    display_name: string;
}

export interface LoginResponse { user: CurrentUserResponse; }
export interface LogoutResponse { success: boolean; }
export interface ChangePasswordResponse { success: boolean; }

export interface PlanetsAccountResponse {
    id: number;
    planets_username: string;
    planets_account_id: number | null;
    profile_image_url: string | null;
    is_active: boolean;
    last_verified_at: string | null;
    last_error: string | null;
}

export interface PlanetsAccountsResponse { accounts: PlanetsAccountResponse[]; }
export interface UnlinkPlanetsAccountResponse { success: boolean; }

export interface AccountGameSummary {
    id: number;
    name: string;
    short_description: string;
    status_id: number;
    status_name: string;
    turn: number;
    slots: number;
    turn_status: string | null;
    next_host: string;
    time_to_host: string;
    is_private: boolean;
    is_custom: boolean;
    data_source: "planets.nu" | "canonical-cache" | string;
    observer_slot_id: number | null;
    observer_status: number | null;
    membership_source: string | null;
}

export interface AccountGamesResponse {
    linked_account_id: number;
    planets_username: string;
    games: AccountGameSummary[];
    upstream_available: boolean;
    upstream_error: string | null;
}

export interface PrivateIntelObserver {
    linked_account_id: number;
    planets_account_id: number | null;
    planets_username: string;
    player_slot_id: number;
    is_active: boolean;
}

export interface PrivateIntelObservationMetadata {
    batch_id: number;
    source: string;
    snapshot_hash: string;
    observed_at: string;
}

export interface PrivateIntelCounts {
    planets: number;
    ships: number;
    starbases: number;
    nebulas: number;
    ion_storms: number;
    star_clusters: number;
    minefields: number;
}

export interface PlanetObservationResponse {
    planet_id: number;
    owner_id: number | null;
    info_turn: number | null;
    name: string | null;
    x: number | null;
    y: number | null;
    payload: Record<string, unknown>;
}

export interface ShipObservationResponse {
    ship_id: number;
    owner_id: number | null;
    info_turn: number | null;
    hull_id: number | null;
    name: string | null;
    x: number | null;
    y: number | null;
    warp: number | null;
    payload: Record<string, unknown>;
}
