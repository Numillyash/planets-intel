import type { ReactNode } from "react";
import type { GameDetailsResponse } from "../../types/api";

export const DASHBOARD_TABS = [
    { id: "dashboard", label: "Dashboard" },
    { id: "turn-review", label: "Turn Review" },
    { id: "vcr", label: "VCR" },
    { id: "battle-planner", label: "Battle Planner" },
    { id: "reports", label: "Reports" },
    { id: "communications", label: "Communications" },
    { id: "commander-intel", label: "Commander intel" },
    { id: "planets", label: "Planets" },
    { id: "starships", label: "Starships" },
    { id: "starbases", label: "Starbases" },
    { id: "scoreboard", label: "Scoreboard" },
    { id: "military-intel", label: "Military intel" },
    { id: "turn-timing", label: "Turn timing" },
    { id: "diplomacy", label: "Diplomacy" },
    { id: "time-machine", label: "Time machine" },
    { id: "advantages", label: "Advantages" },
    { id: "settings", label: "Settings" },
] as const;

export type GameDashboardTab = typeof DASHBOARD_TABS[number]["id"];

export function GameDashboardTabs({
    activeTab, onSelect,
}: {
    activeTab: string;
    onSelect: (tab: GameDashboardTab) => void;
}) {
    return (
        <nav className="game-dashboard-tabs" aria-label="Game dashboard sections">
            {DASHBOARD_TABS.map((tab) => (
                <button
                    className={activeTab === tab.id ? "is-active" : ""}
                    key={tab.id} onClick={() => onSelect(tab.id)} type="button"
                >
                    {tab.label}
                </button>
            ))}
        </nav>
    );
}

export interface DashboardSummary {
    planets: number | string;
    ships: number | string;
    starbases: number | string;
    turnState: string;
    schedule: string;
    nextHost: string;
}

export function GameDashboardOverview({
    game, summary, context, onSelect, action,
}: {
    game: GameDetailsResponse;
    summary: DashboardSummary;
    context: string;
    onSelect: (tab: GameDashboardTab) => void;
    action?: ReactNode;
}) {
    return (
        <>
            <section className="summary-grid game-dashboard-summary">
                <button className="summary-card" onClick={() => onSelect("planets")} type="button">
                    <span>Planets</span><strong>{summary.planets}</strong>
                </button>
                <button className="summary-card" onClick={() => onSelect("starships")} type="button">
                    <span>Starships</span><strong>{summary.ships}</strong>
                </button>
                <button className="summary-card" onClick={() => onSelect("starbases")} type="button">
                    <span>Starbases</span><strong>{summary.starbases}</strong>
                </button>
                <button className="summary-card" onClick={() => onSelect("scoreboard")} type="button">
                    <span>Turn state</span><strong>{summary.turnState}</strong>
                </button>
                <div className="summary-card">
                    <span>Schedule</span><strong>{summary.schedule}</strong>
                </div>
                <div className="summary-card">
                    <span>Next host</span><strong>{summary.nextHost}</strong>
                </div>
            </section>
            <section className="panel game-dashboard-home">
                <div className="panel-header">
                    <div>
                        <h2>{game.game.name}</h2>
                        <p>{context}</p>
                    </div>
                    {action}
                </div>
                <div className="game-dashboard-launch-grid">
                    {DASHBOARD_TABS.filter((tab) => tab.id !== "dashboard").map((tab) => (
                        <button key={tab.id} onClick={() => onSelect(tab.id)} type="button">
                            <strong>{tab.label}</strong>
                            <small>Open section</small>
                        </button>
                    ))}
                </div>
            </section>
        </>
    );
}
