export const VCR_REVIEWED_EVENT = "intel-vcr-reviewed";

export interface ReviewedVcrRecord {
    vcrId: number;
    x: number | null;
    y: number | null;
}

interface VcrReviewedEventDetail extends ReviewedVcrRecord {
    gameId: number;
    turn: number;
}

const STORAGE_PREFIX = "planets-intel:vcr-reviewed";

function storageKey(gameId: number, turn: number): string {
    return `${STORAGE_PREFIX}:${gameId}:${turn}`;
}

function usableInteger(value: unknown): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function usableCoordinate(value: unknown): value is number | null {
    return value === null || (typeof value === "number" && Number.isFinite(value));
}

export function readReviewedVcrs(gameId: number, turn: number): ReviewedVcrRecord[] {
    if (!usableInteger(gameId) || !usableInteger(turn)) return [];

    try {
        const raw = window.localStorage.getItem(storageKey(gameId, turn));
        if (raw === null) return [];
        const parsed = JSON.parse(raw) as unknown;
        if (!Array.isArray(parsed)) return [];

        const result = new Map<number, ReviewedVcrRecord>();
        for (const item of parsed) {
            if (typeof item !== "object" || item === null) continue;
            const candidate = item as Partial<ReviewedVcrRecord>;
            if (
                !usableInteger(candidate.vcrId)
                || !usableCoordinate(candidate.x)
                || !usableCoordinate(candidate.y)
            ) {
                continue;
            }
            result.set(candidate.vcrId, {
                vcrId: candidate.vcrId,
                x: candidate.x,
                y: candidate.y,
            });
        }
        return [...result.values()].sort((left, right) => left.vcrId - right.vcrId);
    } catch {
        return [];
    }
}

export function markVcrReviewed(
    gameId: number,
    turn: number,
    record: ReviewedVcrRecord,
): void {
    if (!usableInteger(gameId) || !usableInteger(turn) || !usableInteger(record.vcrId)) {
        return;
    }

    const next = new Map(
        readReviewedVcrs(gameId, turn).map((item) => [item.vcrId, item] as const),
    );
    next.set(record.vcrId, record);

    try {
        window.localStorage.setItem(
            storageKey(gameId, turn),
            JSON.stringify([...next.values()].sort((left, right) => left.vcrId - right.vcrId)),
        );
    } catch {
        // Browser storage is an optional presentation convenience. The in-page
        // review event still hides the marker for the current session.
    }

    window.dispatchEvent(new CustomEvent<VcrReviewedEventDetail>(VCR_REVIEWED_EVENT, {
        detail: {
            gameId,
            turn,
            vcrId: record.vcrId,
            x: record.x,
            y: record.y,
        },
    }));
}

function routedGameId(): number | null {
    const match = window.location.pathname.match(/^\/intelboard\/[^/]+\/(\d+)\/?$/i);
    if (match === null) return null;
    const value = Number(match[1]);
    return usableInteger(value) ? value : null;
}

export function isVcrReviewedForCurrentRoute(turn: number, vcrId: number): boolean {
    const gameId = routedGameId();
    if (gameId === null) return false;
    return readReviewedVcrs(gameId, turn).some((item) => item.vcrId === vcrId);
}

export function isReviewedCombatPositionForCurrentRoute(
    turn: number,
    x: number,
    y: number,
): boolean {
    const gameId = routedGameId();
    if (gameId === null) return false;
    return readReviewedVcrs(gameId, turn).some(
        (item) => item.x === x && item.y === y,
    );
}
