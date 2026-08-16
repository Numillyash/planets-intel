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
    beam_charge: number | null;
    launcher_charge: number | null;
}

export interface VcrReplayFrame {
    cycle: number;
    seed: number;
    left: VcrReplaySideFrame;
    right: VcrReplaySideFrame;
    events: string[];
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
