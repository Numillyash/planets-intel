import type { VcrReplayFrame } from "./vcrReplay";

export type BattleSimulatorSourceKind =
    | "known_ship"
    | "known_planet"
    | "vcr"
    | "manual";

export type RightBalanceMode = "auto" | "on" | "off";

export interface BattleSimulatorCombatant {
    source_kind: BattleSimulatorSourceKind;
    source_id: number | null;
    name: string | null;
    object_id: number | null;
    owner_id: number | null;
    race_id: number | null;
    hull_id: number;
    has_starbase: boolean;
    physical_beam_count: number | null;
    physical_launcher_count: number | null;
    physical_bay_count: number | null;
    federation_crew_bonus: boolean;
    lizard_crew_bonus: boolean;
    galactic_power: boolean;
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
    planet_defense: number | null;
    starbase_defense: number | null;
    starbase_fighters: number | null;
    starbase_beam_tech: number | null;
    starbase_damage: number | null;
    starbase_mass_bonus: number | null;
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
    frames: VcrReplayFrame[];
    left?: BattleSimulatorTerminalSide;
    right?: BattleSimulatorTerminalSide;
    start_seed?: number;
    right_balance?: {
        eligible: boolean;
        mode: RightBalanceMode;
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
        right_balance_mode: RightBalanceMode;
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

export interface BattleSimulatorSequenceTerminalCombatant extends BattleSimulatorCombatant {
    index: number;
    status: "unfought" | "fighting" | "survived" | "destroyed" | "captured";
}

export interface BattleSimulatorPlanetCarryover {
    basis: string;
    planet_defense: number | null;
    starbase_present: boolean;
    starbase_defense: number | null;
    starbase_fighters: number | null;
    starbase_beam_tech: number | null;
    starbase_damage: number | null;
}

export interface BattleSimulatorSequenceEngagement {
    number: number;
    left_index: number;
    right_index: number;
    start_seed: number;
    right_balance_applied: boolean;
    right_balance_mode?: RightBalanceMode;
    result: string[];
    cycles: number;
    left: BattleSimulatorTerminalSide;
    right: BattleSimulatorTerminalSide;
    planet_carryover?: BattleSimulatorPlanetCarryover;
}

export interface BattleSimulatorSequenceRunResponse {
    game_id: number;
    supported: boolean;
    reason: string | null;
    basis: "standalone_battle_sequence";
    persisted: false;
    right_balance_mode?: RightBalanceMode;
    winner?: "left" | "right" | "draw" | "timeout" | "unknown";
    engagements?: BattleSimulatorSequenceEngagement[];
    left?: BattleSimulatorSequenceTerminalCombatant[];
    right?: BattleSimulatorSequenceTerminalCombatant[];
    sequence_model?: Record<string, unknown>;
}

export interface BattleSimulatorSequenceCombatantOdds {
    index: number;
    name: string | null;
    source_id: number | null;
    fought_count: number;
    fought_percent: number;
    status_counts: Record<string, number>;
    mean_final_shield: number | null;
    mean_final_damage: number | null;
    mean_final_crew: number | null;
    mean_final_torpedoes: number | null;
    mean_final_fighters: number | null;
}

export interface BattleSimulatorSequenceOddsResponse {
    game_id: number;
    supported: boolean;
    reason: string | null;
    basis: "standalone_battle_sequence_sampling";
    persisted: false;
    sample_count: number;
    outcomes?: Array<{
        outcome: string;
        count: number;
        percent: number;
    }>;
    sides?: {
        left: BattleSimulatorSequenceCombatantOdds[];
        right: BattleSimulatorSequenceCombatantOdds[];
    };
    sampling?: {
        requested_battles: number;
        sampling_seed: number | null;
        classic_start_seeds: number;
        right_balance_mode: RightBalanceMode;
        right_balance_probability_when_eligible: number;
        unique_engagement_replays_computed: number;
        mean_engagements: number;
    };
    sequence_model?: Record<string, unknown>;
}

async function postJson<T>(url: string, body: unknown, label: string): Promise<T> {
    const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`${label}: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
}

export function runStandaloneBattle(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant;
        right: BattleSimulatorCombatant;
        seed: number;
        right_balance_bonus: RightBalanceMode;
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorRunResponse> {
    return postJson<BattleSimulatorRunResponse>(
        `/api/games/${gameId}/battle-simulator/run`,
        body,
        "Battle simulator request failed",
    );
}

export function runStandaloneBattleOdds(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant;
        right: BattleSimulatorCombatant;
        battles: number;
        right_balance_bonus: RightBalanceMode;
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorOddsResponse> {
    return postJson<BattleSimulatorOddsResponse>(
        `/api/games/${gameId}/battle-simulator/odds`,
        body,
        "Battle odds request failed",
    );
}

export function runStandaloneBattleSequence(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant[];
        right: BattleSimulatorCombatant[];
        seed: number;
        right_balance_bonus: RightBalanceMode;
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorSequenceRunResponse> {
    return postJson<BattleSimulatorSequenceRunResponse>(
        `/api/games/${gameId}/battle-simulator/sequence/run`,
        body,
        "Battle sequence request failed",
    );
}

export function runStandaloneBattleSequenceOdds(
    gameId: number,
    body: {
        left: BattleSimulatorCombatant[];
        right: BattleSimulatorCombatant[];
        battles: number;
        right_balance_bonus: RightBalanceMode;
        sampling_seed?: number | null;
    },
): Promise<BattleSimulatorSequenceOddsResponse> {
    return postJson<BattleSimulatorSequenceOddsResponse>(
        `/api/games/${gameId}/battle-simulator/sequence/odds`,
        body,
        "Battle sequence odds failed",
    );
}
