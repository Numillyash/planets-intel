export type ThreatRisk = "critical" | "high" | "medium" | "low" | "unknown";

export interface ThreatRaceTrait {
    name: string;
    active: boolean | null;
    basis: string;
}

export interface ThreatBeamCandidate {
    id: number;
    name: string;
    tech_level: number | null;
    mass_each: number | null;
    minimum_hull_plus_beams_mass: number | null;
}

export interface ThreatTorpedoCandidate {
    id: number;
    name: string;
    tech_level: number | null;
}

export interface ThreatVcrReveal {
    battle_turn: number;
    vcr_id: number;
    batch_id: number;
    beam_id: number | null;
    beam_count: number | null;
    torpedo_id: number | null;
    launcher_count: number | null;
    torpedoes: number | null;
    fighters: number | null;
    combat_start_torpedoes?: number | null;
    combat_start_fighters?: number | null;
    post_combat_torpedoes?: number | null;
    post_combat_fighters?: number | null;
    post_combat_turn?: number | null;
    post_combat_vcr_id?: number | null;
    post_combat_source?: string | null;
    crew: number | null;
    damage: number | null;
    mass: number | null;
}

export interface ThreatMassHistoryItem {
    turn: number;
    mass: number;
}

export interface ThreatTarget {
    planet_id: number;
    name: string | null;
    x: number;
    y: number;
    waypoint_distance: number | null;
    distance_from_ship: number | null;
    eta_observed_turns: number | null;
    confidence: "very_high" | "high" | "medium" | "none";
    defense_posts: number | null;
    has_starbase: boolean;
}

export interface ThreatGroupShip {
    ship_id: number;
    name: string | null;
    hull_id: number | null;
    mass: number | null;
    x: number | null;
    y: number | null;
    warp: number | null;
    waypoint_x: number | null;
    waypoint_y: number | null;
}

export interface ThreatDefender {
    ship_id: number;
    name: string | null;
    hull_id: number | null;
    distance_to_target: number;
    within_warp9_reach: boolean;
    combat_hull: boolean;
    beam_slots: number | null;
    tube_slots: number | null;
    fighter_bays: number | null;
    torpedoes: number | null;
    fighters: number | null;
    heavy_weapon_ready: boolean;
}

export interface ThreatMilitaryContext {
    turn: number;
    military_score: number;
    military_delta: number | null;
}

export interface ShipThreatAnalysis {
    game_id: number;
    turn: number;
    ship_id: number;
    status: "ok" | "catalog_missing";
    detail?: string;
    subject?: {
        name: string | null;
        owner_slot_id: number | null;
        owner_username: string | null;
        race_id: number | null;
        race_name: string;
        hull_id: number | null;
        hull_name: string;
        observed_mass: number | null;
        minimum_observed_mass: number | null;
        hull_mass: number | null;
        beam_slots: number | null;
        tube_slots: number | null;
        fighter_bays: number | null;
        info_turn: number | null;
        source_batch_id: number;
    };
    mass_history?: ThreatMassHistoryItem[];
    loadout?: {
        vcr_reveal: ThreatVcrReveal | null;
        beam_candidates: ThreatBeamCandidate[];
        torpedo_candidates: ThreatTorpedoCandidate[];
        mass_excess_over_bare_hull: number | null;
        mass_caveat: string;
    };
    race_traits?: ThreatRaceTrait[];
    target?: ThreatTarget | null;
    attack_group?: ThreatGroupShip[];
    defense?: {
        primary_slot_id: number;
        risk: ThreatRisk;
        reasons: string[];
        reachable_combat_defenders: number;
        reachable_heavy_defenders: number;
        defenders: ThreatDefender[];
    };
    military?: {
        subject_owner: ThreatMilitaryContext | null;
        primary_owner: ThreatMilitaryContext | null;
    };
    provenance?: {
        analysis_kind: "read_time_inference";
        facts_unchanged: boolean;
        accessible_observer_ids: number[];
        rule_catalog_turn: number;
    };
}
