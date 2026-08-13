import { useEffect, useState } from "react";

import { CombatEventPanel as VcrPanel } from "./CombatEventPanelLegacy";
import { HostEventPanel } from "./HostEventPanel";
import { MapEventBridge } from "./MapEventBridge";
import { PlayerActivityPanel } from "./PlayerActivityPanel";
import "./operational-shell-v2.css";

type DashboardTab = "combat" | "host" | "activity";

export function CombatEventPanel(props: Parameters<typeof VcrPanel>[0]) {
    const [dashboardOpen, setDashboardOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<DashboardTab>("combat");

    useEffect(() => {
        const openCombatEvidence = () => {
            setActiveTab("combat");
            setDashboardOpen(true);
        };

        window.addEventListener("dashboard-event-select", openCombatEvidence);
        return () => {
            window.removeEventListener("dashboard-event-select", openCombatEvidence);
        };
    }, []);

    return (
        <>
            <MapEventBridge />

            <div className="operational-map-hud">
                <button
                    aria-label="Open dashboard"
                    className="operational-map-menu-button"
                    onClick={() => setDashboardOpen(true)}
                    type="button"
                >
                    <span aria-hidden="true">☰</span>
                </button>
                <div className="operational-map-turn">
                    <span>TURN</span>
                    <strong>{props.turn}</strong>
                </div>
            </div>

            <div
                aria-hidden={!dashboardOpen}
                className={`operational-dashboard-overlay${dashboardOpen ? " is-open" : ""}`}
            >
                <header className="operational-dashboard-header">
                    <div>
                        <span>PLANETS INTEL</span>
                        <strong>Game dashboard</strong>
                    </div>
                    <button
                        className="operational-dashboard-map-button"
                        onClick={() => setDashboardOpen(false)}
                        type="button"
                    >
                        Starmap
                    </button>
                </header>

                <nav
                    aria-label="Game dashboard sections"
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
                        Host events
                    </button>
                    <button
                        className={activeTab === "activity" ? "is-active" : ""}
                        onClick={() => setActiveTab("activity")}
                        type="button"
                    >
                        Activity
                    </button>
                </nav>

                <div className="operational-dashboard-content">
                    <section
                        className={`operational-dashboard-pane${activeTab === "combat" ? " is-active" : ""}`}
                    >
                        <VcrPanel {...props} />
                    </section>
                    <section
                        className={`operational-dashboard-pane${activeTab === "host" ? " is-active" : ""}`}
                    >
                        <HostEventPanel
                            gameId={props.gameId}
                            linkedAccountId={props.linkedAccountId}
                            turn={props.turn}
                        />
                    </section>
                    <section
                        className={`operational-dashboard-pane${activeTab === "activity" ? " is-active" : ""}`}
                    >
                        <PlayerActivityPanel
                            gameId={props.gameId}
                            throughTurn={props.turn}
                        />
                    </section>
                </div>
            </div>
        </>
    );
}
