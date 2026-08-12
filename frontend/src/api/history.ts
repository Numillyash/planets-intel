import type { LatestPrivateIntelResponse } from "../types/api";
import type {
    CombinedPrivateIntelResponse,
} from "../types/intel";
import type {
    HistoricalBackfillTurnResponse,
    HistoricalIntelStatus,
} from "../types/history";

async function parseErrorMessage(response: Response): Promise<string> {
    try {
        const payload = await response.json() as { detail?: string };
        if (payload.detail) {
            return payload.detail;
        }
    } catch {
        // Fall back to HTTP status below.
    }
    return `${response.status} ${response.statusText}`;
}

async function apiGetOptional<T>(url: string): Promise<T | null> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });

    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        throw new Error(
            `Historical intel request failed: ${await parseErrorMessage(response)}`,
        );
    }
    return response.json() as Promise<T>;
}

export function getHistoricalPrivateIntel(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): Promise<LatestPrivateIntelResponse | null> {
    return apiGetOptional<LatestPrivateIntelResponse>(
        `/api/games/${gameId}/private-intel/history/turn/${turn}`
        + `?linked_account_id=${linkedAccountId}`,
    );
}

export function getHistoricalCombinedIntel(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): Promise<CombinedPrivateIntelResponse | null> {
    return apiGetOptional<CombinedPrivateIntelResponse>(
        `/api/games/${gameId}/private-intel/history/combined/${turn}`
        + `?linked_account_id=${linkedAccountId}`,
    );
}

export async function getHistoricalIntelStatus(
    gameId: number,
    linkedAccountId: number,
): Promise<HistoricalIntelStatus> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/status`
        + `?linked_account_id=${linkedAccountId}`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `Historical status failed: ${await parseErrorMessage(response)}`,
        );
    }
    return response.json() as Promise<HistoricalIntelStatus>;
}

export async function backfillHistoricalTurn(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): Promise<HistoricalBackfillTurnResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/history/backfill/${turn}`
        + `?linked_account_id=${linkedAccountId}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `Historical backfill failed: ${await parseErrorMessage(response)}`,
        );
    }
    return response.json() as Promise<HistoricalBackfillTurnResponse>;
}
