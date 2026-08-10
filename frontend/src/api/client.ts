import type {
    GameDetailsResponse,
    ScoreHistoryResponse,
} from "../types/api";


async function apiGet<T>(url: string): Promise<T> {
    const response = await fetch(url, {
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(
            `API request failed: ${response.status} ${response.statusText}`,
        );
    }

    return response.json() as Promise<T>;
}


export function getGame(
    gameId: number,
): Promise<GameDetailsResponse> {
    return apiGet<GameDetailsResponse>(
        `/api/games/${gameId}`,
    );
}


export function getScoreHistory(
    gameId: number,
): Promise<ScoreHistoryResponse> {
    return apiGet<ScoreHistoryResponse>(
        `/api/games/${gameId}/scores/history`,
    );
}
