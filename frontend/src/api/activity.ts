import type {
    GameActivityResponse,
    HostEventsResponse,
    PlayerActivityResponse,
    SendGameMessageResponse,
} from "../types/activity";


async function responseError(response: Response): Promise<string> {
    let detail = `${response.status} ${response.statusText}`;
    try {
        const payload = await response.json() as { detail?: string };
        if (payload.detail) detail = payload.detail;
    } catch {
        // Keep the status fallback.
    }
    return detail;
}


async function apiGet<T>(url: string): Promise<T> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(`API request failed: ${await responseError(response)}`);
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


export function getGameActivity(
    gameId: number,
    linkedAccountId: number,
    limit = 500,
): Promise<GameActivityResponse> {
    return apiGet<GameActivityResponse>(
        `/api/games/${gameId}/communications?linked_account_id=${linkedAccountId}&limit=${limit}`,
    );
}


export async function sendGameMessage(
    gameId: number,
    linkedAccountId: number,
    recipientPlayerIds: number[],
    body: string,
): Promise<SendGameMessageResponse> {
    const response = await fetch(
        `/api/games/${gameId}/communications/messages`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                linked_account_id: linkedAccountId,
                recipient_player_ids: recipientPlayerIds,
                body,
            }),
        },
    );

    if (!response.ok) {
        throw new Error(`Message send failed: ${await responseError(response)}`);
    }

    return response.json() as Promise<SendGameMessageResponse>;
}
