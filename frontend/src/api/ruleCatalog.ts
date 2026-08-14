export interface GameRuleCatalogResponse {
    game_id: number;
    observed_turn: number;
    settings: Record<string, unknown>;
    races: Array<Record<string, unknown>>;
    advantages: Array<Record<string, unknown>>;
    hulls: Array<Record<string, unknown>>;
}

export async function getGameRuleCatalog(
    gameId: number,
): Promise<GameRuleCatalogResponse> {
    const response = await fetch(
        `/api/games/${gameId}/rule-catalog`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `Rule catalog request failed: ${response.status} ${response.statusText}`,
        );
    }
    return response.json() as Promise<GameRuleCatalogResponse>;
}
