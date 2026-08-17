export interface VcrFighterTrack {
    index: number;
    status: number;
    x: number;
}

export interface VcrReplayEffect {
    kind:
        | "torpedo_launch"
        | "fighter_launch"
        | "fighter_attack"
        | "beam_ship"
        | "beam_fighter"
        | "fighter_dogfight_loss"
        | string;
    source?: "left" | "right";
    target?: "left" | "right";
    lost_side?: "left" | "right";
    count?: number;
    fighter_id?: number;
    x?: number;
    source_x?: number;
    target_x?: number;
}

export interface VcrReplaySideFrame {
    object_id: number | null;
    owner_id: number | null;
    name: string | null;
    hull_id: number;
    image_id: number | null;
    is_planet: boolean;
    x: number;
    shield: number;
    damage: number;
    crew: number;
    torpedoes: number;
    fighters: number;
    fighters_out: number;
    fighter_tracks?: VcrFighterTrack[];
    beam_slots?: number[];
    launcher_slots?: number[];
    beam_charge: number | null;
    launcher_charge: number | null;
}

export interface VcrReplayFrame {
    cycle: number;
    seed: number;
    left: VcrReplaySideFrame;
    right: VcrReplaySideFrame;
    events: string[];
    effects?: VcrReplayEffect[];
}

export interface VcrReplayTraceResponse {
    game_id: number;
    turn: number;
    vcr_id: number;
    supported: boolean;
    reason: string | null;
    engine?: string;
    basis?: string;
    battle_type?: number | null;
    cycles?: number;
    result?: string[];
    frames: VcrReplayFrame[];
}

export interface CombatPlannerSideOverrides {
    fighters?: number | null;
    torpedoes?: number | null;
}

export interface CombatPlannerScenarioRequest {
    left: CombatPlannerSideOverrides;
    right: CombatPlannerSideOverrides;
}

export interface CombatPlannerRepeatRequest extends CombatPlannerScenarioRequest {
    battles: number;
    sampling_seed?: number | null;
}

export interface CombatPlannerAmmoState {
    fighters: number | null;
    torpedoes: number | null;
}

export interface CombatPlannerScenarioResponse extends VcrReplayTraceResponse {
    basis: "battle_planner_scenario";
    source_basis: "factual_vcr";
    engine_basis?: string;
    persisted: false;
    baseline: {
        left: CombatPlannerAmmoState;
        right: CombatPlannerAmmoState;
    };
    assumptions: {
        left: Record<string, number>;
        right: Record<string, number>;
    };
}

export interface CombatPlannerOddsOutcome {
    outcome: string;
    count: number;
    seed_frequency_percent: number;
    representative_seed: number | null;
}

export interface CombatPlannerOddsSide {
    destroyed_count: number;
    captured_count: number;
    survived_count: number;
    survival_seed_frequency_percent: number;
    mean_final_shield: number;
    mean_final_damage: number;
    mean_final_crew: number;
    mean_final_torpedoes: number;
    mean_final_fighters: number;
}

export interface CombatPlannerOddsResponse {
    game_id: number;
    turn: number;
    vcr_id: number;
    supported: boolean;
    reason: string | null;
    basis: "battle_planner_seed_sweep" | "battle_planner_repeat_sampling";
    source_basis: "factual_vcr";
    engine_basis?: string;
    persisted: false;
    baseline: {
        left: CombatPlannerAmmoState;
        right: CombatPlannerAmmoState;
    };
    assumptions: {
        left: Record<string, number>;
        right: Record<string, number>;
    };
    sample_count: number;
    seed_space?: {
        kind: string;
        first: number;
        last: number;
        count: number;
        assumption: string;
    };
    sampling?: {
        mode: string;
        requested_battles: number;
        sampling_seed: number | null;
        unique_start_seed_count: number;
    };
    outcomes: CombatPlannerOddsOutcome[];
    sides: {
        left?: CombatPlannerOddsSide;
        right?: CombatPlannerOddsSide;
    };
}

export async function getVcrReplayTrace(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    vcrId: number,
): Promise<VcrReplayTraceResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/combat-events/${turn}/${vcrId}/replay`
        + `?linked_account_id=${linkedAccountId}`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `VCR replay request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<VcrReplayTraceResponse>;
}

export async function runCombatPlannerScenario(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    vcrId: number,
    scenario: CombatPlannerScenarioRequest,
): Promise<CombatPlannerScenarioResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/combat-events/${turn}/${vcrId}/scenario`
        + `?linked_account_id=${linkedAccountId}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(scenario),
        },
    );
    if (!response.ok) {
        throw new Error(
            `Battle planner request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<CombatPlannerScenarioResponse>;
}

export async function runCombatPlannerOdds(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    vcrId: number,
    scenario: CombatPlannerScenarioRequest,
): Promise<CombatPlannerOddsResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/combat-events/${turn}/${vcrId}/odds`
        + `?linked_account_id=${linkedAccountId}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(scenario),
        },
    );
    if (!response.ok) {
        throw new Error(
            `Battle seed-series request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<CombatPlannerOddsResponse>;
}

export async function runCombatPlannerRepeatOdds(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    vcrId: number,
    scenario: CombatPlannerRepeatRequest,
): Promise<CombatPlannerOddsResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/combat-events/${turn}/${vcrId}/repeat-odds`
        + `?linked_account_id=${linkedAccountId}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(scenario),
        },
    );
    if (!response.ok) {
        throw new Error(
            `Repeated battle simulation failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<CombatPlannerOddsResponse>;
}
