export type GameSurfaceView = "starmap" | "dashboard";

export interface GameSurfaceRoute {
    view: GameSurfaceView;
    tab: string | null;
}

export const GAME_SURFACE_ROUTE_EVENT = "intel-game-surface-route";


function legacyIntelTab(value: string | null): string {
    if (value === "host" || value === "reports") return "reports";
    if (value === "communications") return "communications";
    return "vcr";
}


export function readGameSurfaceRoute(): GameSurfaceRoute {
    const params = new URLSearchParams(window.location.search);
    const rawView = params.get("view");

    if (rawView === "starmap") {
        return { view: "starmap", tab: null };
    }
    if (rawView === "dashboard") {
        return { view: "dashboard", tab: params.get("tab") };
    }
    if (rawView === "intel") {
        return {
            view: "dashboard",
            tab: legacyIntelTab(params.get("tab")),
        };
    }

    const legacy = params.get("intel");
    if (legacy !== null) {
        return {
            view: "dashboard",
            tab: legacyIntelTab(legacy),
        };
    }

    return { view: "starmap", tab: null };
}


export function canonicalizeLegacyGameSurfaceLocation(): boolean {
    const url = new URL(window.location.href);
    const rawView = url.searchParams.get("view");
    const legacy = url.searchParams.get("intel");
    if (rawView !== "intel" && legacy === null) return false;

    const route = readGameSurfaceRoute();
    url.searchParams.delete("intel");
    url.searchParams.set("view", route.view);
    if (route.tab === null || route.tab.trim() === "") {
        url.searchParams.delete("tab");
    } else {
        url.searchParams.set("tab", route.tab);
    }

    const next = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState(null, "", next);
    window.dispatchEvent(new Event(GAME_SURFACE_ROUTE_EVENT));
    return true;
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
