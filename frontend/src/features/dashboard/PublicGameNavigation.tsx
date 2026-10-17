import { writeGameSurfaceRoute } from "../../lib/uiRouteState";

export function PublicGameNavigation({
    mapOpen, archiveAvailable, turn,
}: {
    mapOpen: boolean;
    archiveAvailable: boolean;
    turn: number | null;
}) {
    return (
        <nav aria-label="Game surface navigation"
            className={mapOpen
                ? "public-game-navigation operational-surface-nav is-map"
                : "public-game-navigation operational-page-surface-nav"}>
            <a className="secondary-button public-game-navigation-back" href="/intelboard">
                Games
            </a>
            <button type="button"
                className={!mapOpen ? "primary-button" : "secondary-button"}
                onClick={() => writeGameSurfaceRoute("dashboard", "dashboard")}>
                Dashboard
            </button>
            <button type="button"
                className={mapOpen ? "primary-button" : "secondary-button"}
                disabled={!archiveAvailable}
                onClick={() => writeGameSurfaceRoute("starmap")}>
                Starmap
            </button>
            <button type="button" className="secondary-button public-game-turn"
                onClick={() => writeGameSurfaceRoute("dashboard", "time-machine")}>
                Turn {turn ?? "—"}
            </button>
        </nav>
    );
}
