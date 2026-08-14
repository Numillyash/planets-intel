import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { CombatEventPanel as VcrPanel } from "./CombatEventPanelLegacy";
import { HostEventPanel } from "./HostEventPanel";
import { MapEventBridge } from "./MapEventBridge";
import "./operational-shell-v2.css";
import "./operational-dashboard-bridge.css";

type DashboardTab = "combat" | "host";

export function CombatEventPanel(props: Parameters<typeof VcrPanel>[0]) {
    const [intelOverlayOpen, setIntelOverlayOpen] = useState(false);
    const [pageDashboardOpen, setPageDashboardOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<DashboardTab>("combat");

    useEffect(() => {
        const openCombatEvidence = () => {
            setActiveTab("combat");
            setIntelOverlayOpen(true);
        };

        window.addEventListener("dashboard-event-select", openCombatEvidence);
        return () => {
            window.removeEventListener("dashboard-event-select", openCombatEvidence);
        };
    }, []);

    useEffect(() => {
        return () => {
            document.body.classList.remove("operational-page-dashboard-open");
        };
    }, []);

    function openPageDashboard() {
        setIntelOverlayOpen(false);
        setPageDashboardOpen(true);
        document.body.classList.add("operational-page-dashboard-open");
    }

    function showStarmap() {
        document.body.classList.remove("operational-page-dashboard-open");
        setPageDashboardOpen(false);
    }

    return (
        <>
            <MapEventBridge />

            <div className="operational-map-hud">
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
                    onClick={() => setIntelOverlayOpen(true)}
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
                            onClick={openPageDashboard}
                            type="button"
                        >
                            Dashboard
                        </button>
                        <button
                            className="operational-dashboard-map-button"
                            onClick={() => setIntelOverlayOpen(false)}
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
                        onClick={() => setActiveTab("combat")}
                        type="button"
                    >
                        Combat
                    </button>
                    <button
                        className={activeTab === "host" ? "is-active" : ""}
                        onClick={() => setActiveTab("host")}
                        type="button"
                    >
                        Reports
                    </button>
                </nav>

                <div className="operational-dashboard-content">
                    <section
                        className={
                            `operational-dashboard-pane${activeTab === "combat" ? " is-active" : ""}`
                        }
                    >
                        <VcrPanel {...props} />
                    </section>
                    <section
                        className={
                            `operational-dashboard-pane${activeTab === "host" ? " is-active" : ""}`
                        }
                    >
                        <HostEventPanel
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            turn={props.turn}
                        />
                    </section>
                </div>
            </div>
        </>
    );
}
