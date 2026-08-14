export type PredictionPhase = "move_most" | "intercept";
export type PredictionMode = "waypoint" | "intercept";


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
    predicted_x: number | null;
    predicted_y: number | null;
    requested_distance: number | null;
    max_distance: number | null;
    moved_distance: number | null;
    warp: number | null;
    speed_multiplier: number;
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
