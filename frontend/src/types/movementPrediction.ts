export type PredictionPhase = "tow" | "move_most" | "intercept";
export type PredictionMode = "tow" | "waypoint" | "intercept";
export type TowRole = "tower" | "target";
export type PredictionBlockerClass =
    | "phase_state_required"
    | "implementation_gap"
    | "missing_fact"
    | "dependency_unresolved"
    | "order_ambiguity"
    | "unsupported_host_rule";


export interface ShipMovementPrediction {
    ship_id: number;
    movement_mode: PredictionMode;
    phase: PredictionPhase;
    status: string;
    certain: boolean;
    start_x: number | null;
    start_y: number | null;
    waypoint_x: number | null;
    waypoint_y: number | null;
    target_ship_id: number | null;
    target_x: number | null;
    target_y: number | null;
    target_warp: number | null;
    target_speed_multiplier: number | null;
    target_standard_max_distance: number | null;
    pre_well_x: number | null;
    pre_well_y: number | null;
    warp_well_status: string | null;
    warp_well_planet_id: number | null;
    warp_well_planet_name: string | null;
    warp_well_pull_distance: number | null;
    predicted_x: number | null;
    predicted_y: number | null;
    requested_distance: number | null;
    max_distance: number | null;
    moved_distance: number | null;
    displacement_distance: number | null;
    warp: number | null;
    speed_multiplier: number;
    fuel_status: string;
    movement_mass: number | null;
    fuel_available: number | null;
    fuel_factor: number | null;
    fuel_required: number | null;
    fuel_used: number | null;
    fuel_limited: boolean | null;
    fuel_basis: string;
    fuel_reason: string;
    tow_role: TowRole | null;
    tow_tower_ship_id: number | null;
    tow_target_ship_id: number | null;
    tow_lock_status: string | null;
    blocker_class: PredictionBlockerClass | null;
    blocker_reason: string | null;
    reason: string;
    warnings: string[];
}


export interface DraftMovementPredictionResponse {
    game_id: number;
    linked_account_id: number;
    turn: number;
    intercept_mode: "classic" | "chained";
    basis: "local_order_drafts_geometry";
    host_final: false;
    items: ShipMovementPrediction[];
}
