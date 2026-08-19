export type GameSurfaceView = "starmap" | "dashboard" | "intel";

export interface GameSurfaceRoute {
    view: GameSurfaceView;
    tab: string | null;
}

export const GAME_SURFACE_ROUTE_EVENT = "intel-game-surface-route";

function legacyIntelTab(params: URLSearchParams): string | null {
    const value = params.get("intel");
    if (value === "host") return "reports";
    if (value === "combat" || value === "reports" || value === "communications") {
        return value;
    }
    return null;
}

export function readGameSurfaceRoute(): GameSurfaceRoute {
    const params = new URLSearchParams(window.location.search);
    const rawView = params.get("view");
    if (rawView === "dashboard" || rawView === "intel" || rawView === "starmap") {
        return {
            view: rawView,
            tab: params.get("tab"),
        };
    }

    const legacyTab = legacyIntelTab(params);
    if (legacyTab !== null) {
        return { view: "intel", tab: legacyTab };
    }

    return { view: "starmap", tab: null };
}

export function writeGameSurfaceRoute(
    view: GameSurfaceView,
    tab: string | null = null,
    options: { replace?: boolean } = {},
): void {
    const url = new URL(window.location.href);
    url.searchParams.delete("intel");
    url.searchParams.set("view", view);
    if (tab === null || tab.trim() === "") {
        url.searchParams.delete("tab");
    } else {
        url.searchParams.set("tab", tab);
    }

    const next = `${url.pathname}${url.search}${url.hash}`;
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (next === current) return;

    if (options.replace) {
        window.history.replaceState(null, "", next);
    } else {
        window.history.pushState(null, "", next);
    }
    window.dispatchEvent(new Event(GAME_SURFACE_ROUTE_EVENT));
}

export function subscribeGameSurfaceRoute(listener: () => void): () => void {
    window.addEventListener("popstate", listener);
    window.addEventListener(GAME_SURFACE_ROUTE_EVENT, listener);
    return () => {
        window.removeEventListener("popstate", listener);
        window.removeEventListener(GAME_SURFACE_ROUTE_EVENT, listener);
    };
}
