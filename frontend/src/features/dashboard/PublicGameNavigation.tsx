import type { ReactNode } from "react";
import { writeGameSurfaceRoute } from "../../lib/uiRouteState";

interface Props {
    mapOpen: boolean;
    archiveAvailable: boolean;
    children?: ReactNode;
}

export function PublicGameNavigation({ mapOpen, archiveAvailable, children }: Props) {
    return (
        <nav aria-label="Game surface navigation"
            className={mapOpen ? "public-game-navigation is-map" : "public-game-navigation"}>
            <button type="button" className={mapOpen ? "secondary-button" : "primary-button"}
                onClick={() => writeGameSurfaceRoute("dashboard", "dashboard")}>
                Dashboard
            </button>
            <button type="button" className={mapOpen ? "primary-button" : "secondary-button"}
                disabled={!archiveAvailable}
                onClick={() => writeGameSurfaceRoute("starmap")}>
                Starmap
            </button>
            <button type="button" className="secondary-button"
                onClick={() => writeGameSurfaceRoute("dashboard", "time-machine")}>
                Time machine
            </button>
            <a className="secondary-button public-game-navigation-back" href="/intelboard">
                ← My games
            </a>
            {children}
        </nav>
    );
}
