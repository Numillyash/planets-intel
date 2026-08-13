import type {
    HostEventsResponse,
    PlayerActivityResponse,
} from "../types/activity";


async function apiGet<T>(url: string): Promise<T> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
            const payload = await response.json() as { detail?: string };
            if (payload.detail) detail = payload.detail;
        } catch {
            // Keep the status fallback.
        }
        throw new Error(`API request failed: ${detail}`);
    }

    return response.json() as Promise<T>;
}


export function getPlayerActivity(
    gameId: number,
    throughTurn?: number,
): Promise<PlayerActivityResponse> {
    const suffix = throughTurn === undefined
        ? ""
        : `?through_turn=${throughTurn}`;
    return apiGet<PlayerActivityResponse>(
        `/api/games/${gameId}/activity${suffix}`,
    );
}


export function getHostEvents(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): Promise<HostEventsResponse> {
    return apiGet<HostEventsResponse>(
        `/api/games/${gameId}/private-intel/history/host-events?linked_account_id=${linkedAccountId}&turn=${turn}`,
    );
}
