const LAST_OBSERVER_KEY = "planets-intel:last-observer-account-id";

export function readRememberedObserverId(): number | null {
    try {
        const raw = window.localStorage.getItem(LAST_OBSERVER_KEY);
        if (raw === null) return null;
        const value = Number(raw);
        return Number.isSafeInteger(value) && value > 0 ? value : null;
    } catch {
        return null;
    }
}

export function rememberObserverId(accountId: number | null): void {
    try {
        if (accountId === null) {
            window.localStorage.removeItem(LAST_OBSERVER_KEY);
            return;
        }
        window.localStorage.setItem(LAST_OBSERVER_KEY, String(accountId));
    } catch {
        // UI preference persistence is best-effort only.
    }
}
