export interface BuildEventCandidate {
    turn: number;
    warship_delta: number;
    military_delta: number;
    freighter_delta: number;
    planet_delta: number;
    starbase_delta: number;
    inventory_delta: number;
}

export interface RankedLoadoutCandidate {
    engine_id: number | null;
    engine_name: string | null;
    engine_tech: number | null;
    beam_id: number | null;
    beam_name: string | null;
    beam_tech: number | null;
    torpedo_id: number | null;
    torpedo_name: string | null;
    torpedo_tech: number | null;
    weapon_mass: number | null;
    max_fuel_if_no_cargo_or_ammo: number | null;
    max_fuel_fill_ratio: number | null;
    full_tank_shortfall: number | null;
    build_military_score: number | null;
    build_turn: number | null;
    build_military_delta: number | null;
    build_warship_delta: number | null;
    military_delta_residual: number | null;
    evidence_points: number;
    evidence_grade: "strong" | "moderate" | "weak";
}

export interface ShipLoadoutInference {
    status: "ok" | "catalog_missing";
    detail?: string;
    game_id?: number;
    turn?: number;
    ship_id?: number;
    subject?: {
        name: string | null;
        owner_slot_id: number;
        hull_id: number;
        hull_name: string;
        observed_mass: number | null;
        hull_mass: number | null;
        fuel_capacity: number | null;
        cargo_capacity: number | null;
        engine_count: number;
        beam_slots: number;
        tube_slots: number;
        first_observed_turn: number;
        observed_warp: number | null;
    };
    engine_constraint?: {
        kind: "hard_minimum_tech" | "none";
        unlimited_fuel: boolean;
        observed_warp: number | null;
        min_engine_tech: number | null;
        detail: string;
    };
    military_ledger?: {
        current_turn: number | null;
        military_score: number | null;
        military_delta: number | null;
        warships: number | null;
        warship_delta: number | null;
        freighters: number | null;
        freighter_delta: number | null;
        visible_warships: number;
        visible_noncombat_ships: number;
        candidate_build_events: BuildEventCandidate[];
    };
    vcr_reveal?: {
        vcr_id: number;
        battle_turn: number;
        batch_id: number;
        beam_id: number | null;
        torpedo_id: number | null;
        beam_count: number | null;
        launcher_count: number | null;
    } | null;
    assumptions?: {
        near_full_departure_fuel: "soft_prior" | "disabled_for_unlimited_fuel";
        selected_ship_is_new_build: "not_established";
        military_residual: string;
        first_seen_caveat: string;
        historical_score_link?: string;
    };
    ranked_candidates?: RankedLoadoutCandidate[];
    provenance?: {
        analysis_kind: "read_time_inference";
        facts_unchanged: boolean;
        rule_catalog_turn: number;
        source_batch_id: number;
    };
}
