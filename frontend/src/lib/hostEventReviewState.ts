export const HOST_EVENT_REVIEWED_EVENT = "intel-host-event-reviewed";

const STORAGE_PREFIX = "planets-intel:host-event-reviewed";

function usableInteger(value: unknown): value is number {
    return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function routedGameId(): number | null {
    const match = window.location.pathname.match(/^\/intelboard\/[^/]+\/(\d+)\/?$/i);
    if (match === null) return null;
    const value = Number(match[1]);
    return usableInteger(value) ? value : null;
}

function storageKey(gameId: number, turn: number): string {
    return `${STORAGE_PREFIX}:${gameId}:${turn}`;
}

function readReviewedKeys(gameId: number, turn: number): Set<string> {
    if (!usableInteger(gameId) || !usableInteger(turn)) return new Set();

    try {
        const raw = window.localStorage.getItem(storageKey(gameId, turn));
        if (raw === null) return new Set();
        const parsed = JSON.parse(raw) as unknown;
        if (!Array.isArray(parsed)) return new Set();
        return new Set(
            parsed.filter(
                (value): value is string => typeof value === "string" && value.length > 0,
            ),
        );
    } catch {
        return new Set();
    }
}

export function isHostEventReviewedForCurrentRoute(
    turn: number,
    visualKey: string,
): boolean {
    const gameId = routedGameId();
    if (gameId === null || !usableInteger(turn) || visualKey.length === 0) {
        return false;
    }
    return readReviewedKeys(gameId, turn).has(visualKey);
}

export function markHostEventReviewedForCurrentRoute(
    turn: number,
    visualKey: string,
): void {
    const gameId = routedGameId();
    if (gameId === null || !usableInteger(turn) || visualKey.length === 0) {
        return;
    }

    const reviewed = readReviewedKeys(gameId, turn);
    reviewed.add(visualKey);

    try {
        window.localStorage.setItem(
            storageKey(gameId, turn),
            JSON.stringify([...reviewed].sort()),
        );
    } catch {
        // Persistence is optional. The caller still hides the notification in
        // the current Pixi scene immediately after it is reviewed.
    }

    window.dispatchEvent(new CustomEvent(HOST_EVENT_REVIEWED_EVENT, {
        detail: { gameId, turn, visualKey },
    }));
}
