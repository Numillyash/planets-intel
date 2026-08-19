import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

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

function dashboardTabFromLocation(): DashboardTab | null {
    const value = new URLSearchParams(window.location.search).get("intel");
    if (value === "combat") return "combat";
    if (value === "reports" || value === "host") return "host";
    if (value === "communications") return "communications";
    return null;
}

function dashboardTabQueryValue(tab: DashboardTab): string {
    return tab === "host" ? "reports" : tab;
}

function replaceIntelTabInLocation(tab: DashboardTab | null): void {
    const url = new URL(window.location.href);
    if (tab === null) {
        url.searchParams.delete("intel");
    } else {
        url.searchParams.set("intel", dashboardTabQueryValue(tab));
    }
    window.history.replaceState(
        null,
        "",
        `${url.pathname}${url.search}${url.hash}`,
    );
}

export function CombatEventPanel(props: CombatEventPanelProps) {
    const [initialIntelTab] = useState<DashboardTab | null>(
        () => dashboardTabFromLocation(),
    );
    const [intelOverlayOpen, setIntelOverlayOpen] = useState(
        () => initialIntelTab !== null,
    );
    const [pageDashboardOpen, setPageDashboardOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<DashboardTab>(
        () => initialIntelTab ?? "combat",
    );
    const [requestedVcrId, setRequestedVcrId] = useState<number | null>(null);
    const [vcrPopupOpen, setVcrPopupOpen] = useState(false);

    function openIntelTab(tab: DashboardTab) {
        setVcrPopupOpen(false);
        if (tab === "combat") setRequestedVcrId(null);
        setActiveTab(tab);
        setIntelOverlayOpen(true);
        setPageDashboardOpen(false);
        document.body.classList.remove("operational-page-dashboard-open");
        replaceIntelTabInLocation(tab);
    }

    function closeIntelOverlay() {
        setIntelOverlayOpen(false);
        replaceIntelTabInLocation(null);
    }

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
            replaceIntelTabInLocation(null);
        };
        const openHostEvidence = () => {
            setVcrPopupOpen(false);
            setActiveTab("host");
            setIntelOverlayOpen(true);
            setPageDashboardOpen(false);
            document.body.classList.remove("operational-page-dashboard-open");
            replaceIntelTabInLocation("host");
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
        const handlePopState = () => {
            setVcrPopupOpen(false);
            const tab = dashboardTabFromLocation();
            if (tab === null) {
                setIntelOverlayOpen(false);
                return;
            }
            if (tab === "combat") setRequestedVcrId(null);
            setActiveTab(tab);
            setIntelOverlayOpen(true);
        };
        window.addEventListener("popstate", handlePopState);
        return () => window.removeEventListener("popstate", handlePopState);
    }, []);

    useEffect(() => {
        return () => {
            document.body.classList.remove("operational-page-dashboard-open");
        };
    }, []);

    function openPageDashboard() {
        setVcrPopupOpen(false);
        closeIntelOverlay();
        setPageDashboardOpen(true);
        document.body.classList.add("operational-page-dashboard-open");
    }

    function showStarmap() {
        document.body.classList.remove("operational-page-dashboard-open");
        setPageDashboardOpen(false);
    }

    function returnToGameMenu() {
        window.location.assign("/intelboard");
    }

    return (
        <>
            <div className="operational-map-hud">
                <button
                    aria-label="Return to game menu"
                    className="operational-map-menu-button"
                    onClick={returnToGameMenu}
                    title="Game menu"
                    type="button"
                >
                    <span aria-hidden="true">⌂</span>
                </button>
                <button
                    aria-label="Open dashboard"
                    className="operational-map-menu-button"
                    onClick={openPageDashboard}
                    title="Open full game dashboard"
                    type="button"
                >
                    <span aria-hidden="true">☰</span>
                </button>
                <div className="operational-map-turn">
                    <span>TURN</span>
                    <strong>{props.turn}</strong>
                </div>
                <button
                    className="operational-map-intel-button"
                    onClick={() => openIntelTab(activeTab)}
                    type="button"
                >
                    Intel
                </button>
            </div>

            {pageDashboardOpen && createPortal(
                <button
                    className="operational-starmap-return"
                    onClick={showStarmap}
                    type="button"
                >
                    Starmap
                </button>,
                document.body,
            )}

            {vcrPopupOpen && createPortal(
                <div
                    className="operational-vcr-popup-backdrop"
                    onMouseDown={(event) => {
                        if (event.target === event.currentTarget) {
                            setVcrPopupOpen(false);
                        }
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
                className={
                    `operational-dashboard-overlay${intelOverlayOpen ? " is-open" : ""}`
                }
            >
                <header className="operational-dashboard-header">
                    <div>
                        <span>PLANETS INTEL</span>
                        <strong>Intelligence</strong>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                        <button
                            className="operational-dashboard-map-button"
                            onClick={returnToGameMenu}
                            type="button"
                        >
                            Games
                        </button>
                        <button
                            className="operational-dashboard-map-button"
                            onClick={openPageDashboard}
                            type="button"
                        >
                            Dashboard
                        </button>
                        <button
                            className="operational-dashboard-map-button"
                            onClick={closeIntelOverlay}
                            type="button"
                        >
                            Starmap
                        </button>
                    </div>
                </header>

                <nav
                    aria-label="Intelligence sections"
                    className="operational-dashboard-tabs"
                >
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
                    <section
                        className={
                            `operational-dashboard-pane${activeTab === "combat" ? " is-active" : ""}`
                        }
                    >
                        <VcrDashboardPanel
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            turn={props.turn}
                        />
                    </section>
                    <section
                        className={
                            `operational-dashboard-pane${activeTab === "host" ? " is-active" : ""}`
                        }
                    >
                        <HostEventPanel
                            embedded
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            onFocus={(event) => {
                                props.onFocus(event);
                                closeIntelOverlay();
                            }}
                            turn={props.turn}
                        />
                    </section>
                    <section
                        className={
                            `operational-dashboard-pane${activeTab === "communications" ? " is-active" : ""}`
                        }
                    >
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
