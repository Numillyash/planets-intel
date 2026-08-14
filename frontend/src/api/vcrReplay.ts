export interface VcrReplaySideFrame {
    object_id: number | null;
    owner_id: number | null;
    name: string | null;
    hull_id: number;
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
