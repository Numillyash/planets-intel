import { useEffect, useState } from "react";

import { getDraftMovementPrediction } from "../../api/movementPrediction";
import type { DraftMovementPredictionResponse } from "../../types/movementPrediction";
import {
    cacheMovementPrediction,
    clearMovementPrediction,
} from "./movementPredictionState";


export function useMovementPrediction(
    gameId: number,
    linkedAccountId: number | null,
    turn: number,
): DraftMovementPredictionResponse | null {
    const [prediction, setPrediction] =
        useState<DraftMovementPredictionResponse | null>(null);
    const [revision, setRevision] = useState(0);

    useEffect(() => {
        const handleChanged = (event: Event) => {
            const detail = (event as CustomEvent<{
                gameId?: number;
                linkedAccountId?: number;
                turn?: number;
            }>).detail;
            if (
                detail?.gameId !== gameId
                || detail?.linkedAccountId !== linkedAccountId
                || detail?.turn !== turn
            ) {
                return;
            }
            setRevision((value) => value + 1);
        };
        window.addEventListener("intel-order-drafts-changed", handleChanged);
        return () => {
            window.removeEventListener("intel-order-drafts-changed", handleChanged);
        };
    }, [gameId, linkedAccountId, turn]);

    useEffect(() => {
        let cancelled = false;
        if (linkedAccountId === null) return () => { cancelled = true; };
        void getDraftMovementPrediction(gameId, linkedAccountId, turn)
            .then((value) => {
                if (cancelled) return;
                cacheMovementPrediction(value);
                setPrediction(value);
            })
            .catch(() => {
                if (cancelled) return;
                clearMovementPrediction(gameId, linkedAccountId, turn);
                setPrediction(null);
            });
        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, revision, turn]);

    return prediction;
}
