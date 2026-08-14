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

    warp: number | null;
    waypoint_x: number | null;
    waypoint_y: number | null;

    changed_warp: boolean;
    changed_waypoint: boolean;
    source: "local_order_draft";
}

export interface ShipOrderDraftUpdate {
    warp?: number;
    waypoint_x?: number;
    waypoint_y?: number;
}
