import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import {
    canonicalizeLegacyGameSurfaceLocation,
    readGameSurfaceRoute,
    subscribeGameSurfaceRoute,
    writeGameSurfaceRoute,
    type GameSurfaceView,
} from "../../lib/uiRouteState";
import { VcrDashboardPanel } from "../dashboard/VcrDashboardPanel";
import "./operational-shell-v2.css";
import "./operational-dashboard-bridge.css";


interface FocusTarget {
    x: number | null;
    y: number | null;
}

interface CombatEventPanelProps {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    onFocus(event: FocusTarget): void;
}

interface CombatSelectionDetail {
    vcrId?: number;
}


function GameSurfaceNav({
    view,
    turn,
    onGames,
    onDashboard,
    onStarmap,
    className = "",
}: {
    view: GameSurfaceView;
    turn: number;
    onGames(): void;
    onDashboard(): void;
    onStarmap(): void;
    className?: string;
}) {
    return (
        <div className={`operational-surface-nav ${className}`.trim()}>
            <button
                className="operational-dashboard-map-button"
                onClick={onGames}
                type="button"
            >
                Games
            </button>
            <button
                className="operational-dashboard-map-button"
                disabled={view === "dashboard"}
                onClick={onDashboard}
                type="button"
            >
                Dashboard
            </button>
            <button
                className="operational-dashboard-map-button"
                disabled={view === "starmap"}
                onClick={onStarmap}
                type="button"
            >
                Starmap
            </button>
            <div className="operational-map-turn">
                <span>TURN</span>
                <strong>{turn}</strong>
            </div>
        </div>
    );
}


export function CombatEventPanel(props: CombatEventPanelProps) {
    const [initialRoute] = useState(() => readGameSurfaceRoute());
    const [pageDashboardOpen, setPageDashboardOpen] = useState(
        () => initialRoute.view === "dashboard",
    );
    const [requestedVcrId, setRequestedVcrId] = useState<number | null>(null);
    const [vcrPopupOpen, setVcrPopupOpen] = useState(false);

    function applyRouteState() {
        canonicalizeLegacyGameSurfaceLocation();
        const route = readGameSurfaceRoute();
        if (route.view === "dashboard") {
            setPageDashboardOpen(true);
            document.body.classList.add("operational-page-dashboard-open");
            return;
        }
        setPageDashboardOpen(false);
        document.body.classList.remove("operational-page-dashboard-open");
    }

    function showStarmap() {
        setVcrPopupOpen(false);
        writeGameSurfaceRoute("starmap");
    }

    function openPageDashboard(tab = "dashboard") {
        setVcrPopupOpen(false);
        writeGameSurfaceRoute("dashboard", tab);
    }

    function returnToGameMenu() {
        window.location.assign("/intelboard");
    }

    useEffect(() => {
        applyRouteState();
        return subscribeGameSurfaceRoute(applyRouteState);
    }, []);

    useEffect(() => {
        const openCombatEvidence = (rawEvent: Event) => {
            const detail = (rawEvent as CustomEvent<CombatSelectionDetail>).detail;
            const vcrId = typeof detail?.vcrId === "number"
                && Number.isSafeInteger(detail.vcrId)
                && detail.vcrId > 0
                ? detail.vcrId
                : null;
            setRequestedVcrId(vcrId);
            setVcrPopupOpen(true);
            setPageDashboardOpen(false);
            document.body.classList.remove("operational-page-dashboard-open");
        };
        const openHostEvidence = () => {
            setVcrPopupOpen(false);
            openPageDashboard("reports");
        };

        window.addEventListener("dashboard-event-select", openCombatEvidence);
        window.addEventListener("dashboard-host-event-select", openHostEvidence);
        return () => {
            window.removeEventListener("dashboard-event-select", openCombatEvidence);
            window.removeEventListener("dashboard-host-event-select", openHostEvidence);
        };
    }, []);

    useEffect(() => {
        setRequestedVcrId(null);
        setVcrPopupOpen(false);
    }, [props.gameId, props.turn]);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") setVcrPopupOpen(false);
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    useEffect(() => {
        return () => {
            document.body.classList.remove("operational-page-dashboard-open");
        };
    }, []);

    const navProps = {
        turn: props.turn,
        onGames: returnToGameMenu,
        onDashboard: () => openPageDashboard("dashboard"),
        onStarmap: showStarmap,
    };
    const pageSurfaceNavRoot = document.getElementById(
        "operational-page-surface-nav-root",
    );

    return (
        <>
            <GameSurfaceNav
                {...navProps}
                className="operational-map-hud"
                view="starmap"
            />

            {pageDashboardOpen && pageSurfaceNavRoot !== null && createPortal(
                <GameSurfaceNav
                    {...navProps}
                    className="operational-page-surface-nav"
                    view="dashboard"
                />,
                pageSurfaceNavRoot,
            )}

            {vcrPopupOpen && createPortal(
                <div
                    className="operational-vcr-popup-backdrop"
                    onMouseDown={(event) => {
                        if (event.target === event.currentTarget) setVcrPopupOpen(false);
                    }}
                >
                    <section
                        aria-label={`VCR review for turn ${props.turn}`}
                        aria-modal="true"
                        className="operational-vcr-popup"
                        role="dialog"
                    >
                        <header className="operational-vcr-popup-header">
                            <div>
                                <span>COMBAT REVIEW</span>
                                <strong>Turn {props.turn} VCRs</strong>
                            </div>
                            <button
                                className="operational-dashboard-map-button"
                                onClick={() => setVcrPopupOpen(false)}
                                type="button"
                            >
                                Close
                            </button>
                        </header>
                        <div className="operational-vcr-popup-content">
                            <VcrDashboardPanel
                                gameId={props.gameId}
                                initialVcrId={requestedVcrId}
                                linkedAccountId={props.linkedAccountId}
                                turn={props.turn}
                            />
                        </div>
                    </section>
                </div>,
                document.body,
            )}
        </>
    );
}
