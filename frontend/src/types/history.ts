export interface HistoricalIntelAccountCoverage {
    linked_account_id: number;
    planets_username: string;
    is_owned: boolean;
    participates_in_game: boolean;
    turns: number[];
}

export interface HistoricalIntelStatus {
    game_id: number;
    current_turn: number;
    primary_linked_account_id: number;
    accounts: HistoricalIntelAccountCoverage[];
    available_turns: number[];
    complete_turns: number[];
}

export type HistoricalBackfillStatus =
    | "stored"
    | "cached"
    | "skipped"
    | "unavailable"
    | "failed";

export interface HistoricalBackfillAccountResult {
    linked_account_id: number;
    planets_username: string;
    status: HistoricalBackfillStatus;
    detail: string | null;
}

export interface HistoricalBackfillTurnResponse {
    game_id: number;
    turn: number;
    accounts: number;
    stored: number;
    cached: number;
    skipped: number;
    unavailable: number;
    failed: number;
    results: HistoricalBackfillAccountResult[];
}
