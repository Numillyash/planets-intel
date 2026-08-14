import type { DraftMovementPredictionResponse } from "../../types/movementPrediction";


const predictionCache = new Map<string, DraftMovementPredictionResponse>();


function key(gameId: number, linkedAccountId: number, turn: number): string {
    return `${gameId}:${linkedAccountId}:${turn}`;
}


export function cacheMovementPrediction(
    prediction: DraftMovementPredictionResponse,
): void {
    predictionCache.set(
        key(
            prediction.game_id,
            prediction.linked_account_id,
            prediction.turn,
        ),
        prediction,
    );
}


export function clearMovementPrediction(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): void {
    predictionCache.delete(key(gameId, linkedAccountId, turn));
}


export function getCachedMovementPrediction(
    gameId: number,
    linkedAccountId: number,
    turn: number,
): DraftMovementPredictionResponse | null {
    return predictionCache.get(key(gameId, linkedAccountId, turn)) ?? null;
}
