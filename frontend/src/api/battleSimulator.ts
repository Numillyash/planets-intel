export type BattleSimulatorSourceKind =
    | "known_ship"
    | "known_planet"
    | "vcr"
    | "manual";

export interface BattleSimulatorCombatant {
    source_kind: BattleSimulatorSourceKind;
    source_id: number | null;
    name: string | null;
    object_id: number | null;
    owner_id: number | null;
    race_id: number | null;
    hull_id: number;
    has_starbase: boolean;
    beam_count: number;
    launcher_count: number;
    bay_count: number;
    beam_id: number;
    torpedo_id: number;
    shield: number;
    damage: number;
    crew: number;
    mass: number;
    torpedoes: number;
    fighters: number;
    beam_kill_rate: number;
    beam_charge_rate: number;
    torp_charge_rate: number;
    torp_miss_rate: number;
    crew_defense_rate: number;
    notes: string[];
}

export interface BattleSimulatorTerminalSide {
    object_id: number | null;
    owner_id: number | null;
    name: string | null;
    is_planet: boolean;
    shield: number;
    damage: number;
    crew: number;
    torpedoes: number;
    fighters: number;
    destroyed: boolean;
    captured: boolean;
    survived: boolean;
}

export interface BattleSimulatorRunResponse {
    game_id: number;
    supported: boolean;
    reason: string | null;
    basis: "standalone_battle_simulator";
    persisted: false;
    engine?: string;
    cycles?: number;
    result?: string[];
    left?: BattleSimulatorTerminalSide;
    right?: BattleSimulatorTerminalSide;
    start_seed?: number;
    right_balance?: {
        eligible: boolean;
        mode: "auto" | "on" | "off";
        applied: boolean;
        mass_bonus: number;
    };
}

export interface BattleSimulatorOddsSide {
    destroyed_count: number;
    captured_count: number;
    survived_count: number;
    destroyed_percent: number;
    captured_percent: number;
    survived_percent: number;
    mean_final_shield: number;
    mean_final_damage: number;
    mean_final_crew: number;
    mean_final_torpedoes: number;
    mean_final_fighters: number;
}

export interface BattleSimulatorOddsResponse {
    game_id: number;
    supported: boolean;
    reason: string | null;
    basis: "standalone_battle_simulator_sampling";
    persisted: false;
    sample_count: number;
    sampling?: {
        requested_battles: number;
        sampling_seed: number | null;
        classic_start_seeds: number;
        right_balance_eligible: boolean;
        right_balance_probability: number;
        unique_terminal_replays_computed: number;
    };
    outcomes: Array<{
        outcome: string;
        count: number;
        percent: number;
    }>;
    sides: {
        left?: BattleSimulatorOddsSide;
        right?: BattleSimulatorOddsSide;
    };
}

export async function runStandaloneBattle(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant;
        right: BattleSimulatorCombatant;
        seed: number;
        right_balance_bonus: "auto" | "on" | "off";
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorRunResponse> {
    const response = await fetch(`/api/games/${gameId}/battle-simulator/run`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(
            `Battle simulator request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<BattleSimulatorRunResponse>;
}

export async function runStandaloneBattleOdds(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant;
        right: BattleSimulatorCombatant;
        battles: number;
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorOddsResponse> {
    const response = await fetch(`/api/games/${gameId}/battle-simulator/odds`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(
            `Battle odds request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<BattleSimulatorOddsResponse>;
}
