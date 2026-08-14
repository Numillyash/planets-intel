import type { DraftMovementPredictionResponse } from "../types/movementPrediction";


async function parseError(response: Response): Promise<string> {
    try {
        const payload = await response.json() as { detail?: string };
        if (payload.detail) return payload.detail;
    } catch {
        // fall through
    }
    return `${response.status} ${response.statusText}`;
}


export async function getDraftMovementPrediction(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): Promise<DraftMovementPredictionResponse> {
    const response = await fetch(
        `/api/games/${gameId}/movement-prediction`
        + `?turn=${turn}&linked_account_id=${linkedAccountId}`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `Movement prediction failed: ${await parseError(response)}`,
        );
    }
    return response.json() as Promise<DraftMovementPredictionResponse>;
}
