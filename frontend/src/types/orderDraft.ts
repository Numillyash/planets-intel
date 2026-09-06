export type ShipDraftMovementMode = "waypoint" | "intercept";
export type StarbasePrimaryOrder =
    | "none"
    | "refuel"
    | "max_defense"
    | "load_torpedoes"
    | "unload_freighters"
    | "repair_base"
    | "force_surrender";

export interface ShipOrderDraft {
    game_id: number;
    linked_account_id: number;
    turn: number;
    ship_id: number;
    base_batch_id: number;
    base_snapshot_hash: string;
    stale: boolean;

    upstream_warp: number | null;
    upstream_waypoint_x: number | null;
    upstream_waypoint_y: number | null;
    upstream_friendly_code: string | null;
    upstream_mission: string | null;
    upstream_primary_enemy_id: number | null;
    upstream_tow_target_ship_id: number | null;

    warp: number | null;
    waypoint_x: number | null;
    waypoint_y: number | null;
    movement_mode: ShipDraftMovementMode;
    intercept_target_ship_id: number | null;
    tow_target_ship_id: number | null;
    friendly_code: string | null;
    mission: string | null;
    primary_enemy_id: number | null;

    changed_warp: boolean;
    changed_waypoint: boolean;
    changed_movement: boolean;
    changed_tow_target: boolean;
    changed_friendly_code: boolean;
    changed_mission: boolean;
    changed_primary_enemy: boolean;
    source: "local_order_draft";
}

export interface ShipOrderDraftUpdate {
    warp?: number;
    waypoint_x?: number;
    waypoint_y?: number;
    movement_mode?: ShipDraftMovementMode;
    intercept_target_ship_id?: number;
    tow_target_ship_id?: number;
    friendly_code?: string;
    mission?: string;
    primary_enemy_id?: number;
}

export interface PlanetOrderDraft {
    game_id: number;
    linked_account_id: number;
    turn: number;
    planet_id: number;
    base_batch_id: number;
    base_snapshot_hash: string;
    stale: boolean;
    upstream_friendly_code: string | null;
    friendly_code: string | null;
    changed_friendly_code: boolean;
    source: "local_order_draft";
}

export interface StarbaseOrderDraft {
    game_id: number;
    linked_account_id: number;
    turn: number;
    starbase_id: number;
    planet_id: number;
    base_batch_id: number;
    base_snapshot_hash: string;
    stale: boolean;
    upstream_primary_order: string | null;
    primary_order: StarbasePrimaryOrder;
    changed_primary_order: boolean;
    source: "local_order_draft";
}
