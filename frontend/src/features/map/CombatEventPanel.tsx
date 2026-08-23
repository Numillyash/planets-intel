import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import {
    readGameSurfaceRoute,
    subscribeGameSurfaceRoute,
    writeGameSurfaceRoute,
    type GameSurfaceView,
} from "../../lib/uiRouteState";
import { VcrDashboardPanel } from "../dashboard/VcrDashboardPanel";
import { CommunicationsPanel } from "./CommunicationsPanel";
import { HostEventPanel } from "./HostEventPanel";
import "./operational-shell-v2.css";
import "./operational-dashboard-bridge.css";

type DashboardTab = "combat" | "host" | "communications";

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

function intelTabFromRoute(value: string | null): DashboardTab {
    if (value === "reports" || value === "host") return "host";
    if (value === "communications") return "communications";
    return "combat";
}

function intelTabRouteValue(tab: DashboardTab): string {
    return tab === "host" ? "reports" : tab;
}

function GameSurfaceNav({
    view,
    turn,
    onGames,
    onDashboard,
    onIntel,
    onStarmap,
    className = "",
}: {
    view: GameSurfaceView;
    turn: number;
    onGames(): void;
    onDashboard(): void;
    onIntel(): void;
    onStarmap(): void;
    className?: string;
}) {
    return (
        <div className={`operational-surface-nav ${className}`.trim()}>
            <button className="operational-dashboard-map-button" onClick={onGames} type="button">
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
                disabled={view === "intel"}
                onClick={onIntel}
                type="button"
            >
                Intel
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
    const [intelOverlayOpen, setIntelOverlayOpen] = useState(
        () => initialRoute.view === "intel",
    );
    const [pageDashboardOpen, setPageDashboardOpen] = useState(
        () => initialRoute.view === "dashboard",
    );
    const [activeTab, setActiveTab] = useState<DashboardTab>(
        () => intelTabFromRoute(initialRoute.view === "intel" ? initialRoute.tab : null),
    );
    const [requestedVcrId, setRequestedVcrId] = useState<number | null>(null);
    const [vcrPopupOpen, setVcrPopupOpen] = useState(false);

    function applyRouteState() {
        const route = readGameSurfaceRoute();
        if (route.view === "dashboard") {
            setIntelOverlayOpen(false);
            setPageDashboardOpen(true);
            document.body.classList.add("operational-page-dashboard-open");
            return;
        }
        document.body.classList.remove("operational-page-dashboard-open");
        setPageDashboardOpen(false);
        if (route.view === "intel") {
            setActiveTab(intelTabFromRoute(route.tab));
            setIntelOverlayOpen(true);
            return;
        }
        setIntelOverlayOpen(false);
    }

    function openIntelTab(tab: DashboardTab) {
        setVcrPopupOpen(false);
        if (tab === "combat") setRequestedVcrId(null);
        setActiveTab(tab);
        writeGameSurfaceRoute("intel", intelTabRouteValue(tab));
    }

    function showStarmap() {
        setVcrPopupOpen(false);
        writeGameSurfaceRoute("starmap");
    }

    function openPageDashboard() {
        setVcrPopupOpen(false);
        writeGameSurfaceRoute("dashboard", "dashboard");
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
            setIntelOverlayOpen(false);
            setPageDashboardOpen(false);
            document.body.classList.remove("operational-page-dashboard-open");
        };
        const openHostEvidence = () => {
            setVcrPopupOpen(false);
            openIntelTab("host");
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
        onDashboard: openPageDashboard,
        onIntel: () => openIntelTab(activeTab),
        onStarmap: showStarmap,
    };
    const pageSurfaceNavRoot = document.getElementById(
        "operational-page-surface-nav-root",
    );

    return (
        <>
            <GameSurfaceNav {...navProps} className="operational-map-hud" view="starmap" />

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

            <div
                aria-hidden={!intelOverlayOpen}
                className={`operational-dashboard-overlay${intelOverlayOpen ? " is-open" : ""}`}
            >
                <header className="operational-dashboard-header">
                    <div>
                        <span>PLANETS INTEL</span>
                        <strong>Intelligence</strong>
                    </div>
                    <GameSurfaceNav {...navProps} view="intel" />
                </header>

                <nav aria-label="Intelligence sections" className="operational-dashboard-tabs">
                    <button
                        className={activeTab === "combat" ? "is-active" : ""}
                        onClick={() => openIntelTab("combat")}
                        type="button"
                    >
                        Combat
                    </button>
                    <button
                        className={activeTab === "host" ? "is-active" : ""}
                        onClick={() => openIntelTab("host")}
                        type="button"
                    >
                        Reports
                    </button>
                    <button
                        className={activeTab === "communications" ? "is-active" : ""}
                        onClick={() => openIntelTab("communications")}
                        type="button"
                    >
                        Communications
                    </button>
                </nav>

                <div className="operational-dashboard-content">
                    <section className={`operational-dashboard-pane${activeTab === "combat" ? " is-active" : ""}`}>
                        <VcrDashboardPanel
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            turn={props.turn}
                        />
                    </section>
                    <section className={`operational-dashboard-pane${activeTab === "host" ? " is-active" : ""}`}>
                        <HostEventPanel
                            embedded
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            onFocus={(event) => {
                                props.onFocus(event);
                                showStarmap();
                            }}
                            turn={props.turn}
                        />
                    </section>
                    <section className={`operational-dashboard-pane${activeTab === "communications" ? " is-active" : ""}`}>
                        <CommunicationsPanel
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                        />
                    </section>
                </div>
            </div>
        </>
    );
}
