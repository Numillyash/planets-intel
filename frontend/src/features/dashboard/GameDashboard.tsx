import { useState } from "react";

import type {
    GameDetailsResponse,
    LatestPrivateIntelResponse,
    PlanetsAccountResponse,
    ScoreHistoryItem,
    ScoreHistoryResponse,
} from "../../types/api";
import { HostEventPanel } from "../map/HostEventPanel";
import { PlayerActivityPanel } from "../map/PlayerActivityPanel";
import {
    formatInteger,
    planetFacts,
} from "../map/observationView";
import { PlayersTable } from "../players/PlayersTable";
import { MilitaryScoreChart } from "../statistics/MilitaryScoreChart";
import { AdvantagesPanel } from "./AdvantagesPanel";
import { DiplomacyPanel } from "./DiplomacyPanel";
import { StarbaseListPanel } from "./StarbaseListPanel";
import { StarshipListPanel } from "./StarshipListPanel";
import { TimeMachinePanel } from "./TimeMachinePanel";
import { VcrDashboardPanel } from "./VcrDashboardPanel";
import "./game-dashboard.css";

type GameDashboardTab =
    | "dashboard"
    | "vcr"
    | "reports"
    | "planets"
    | "starships"
    | "starbases"
    | "scoreboard"
    | "diplomacy"
    | "time-machine"
    | "advantages"
    | "settings";

const TABS: Array<{ id: GameDashboardTab; label: string }> = [
    { id: "dashboard", label: "Dashboard" },
    { id: "vcr", label: "VCR" },
    { id: "reports", label: "Reports" },
    { id: "planets", label: "Planets" },
    { id: "starships", label: "Starships" },
    { id: "starbases", label: "Starbases" },
    { id: "scoreboard", label: "Scoreboard" },
    { id: "diplomacy", label: "Diplomacy" },
    { id: "time-machine", label: "Time machine" },
    { id: "advantages", label: "Advantages" },
    { id: "settings", label: "Settings" },
];

function playerName(
    game: GameDetailsResponse,
    slotId: number | null,
): string {
    if (slotId === null || slotId <= 0) return "Unowned / unknown";
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} (slot ${slotId})` : `slot ${slotId}`;
}

function Placeholder({
    title,
    children,
}: {
    title: string;
    children: string;
}) {
    return (
        <section className="panel game-dashboard-placeholder">
            <div className="eyebrow">Operational client roadmap</div>
            <h2>{title}</h2>
            <p>{children}</p>
        </section>
    );
}

export function GameDashboard({
    game,
    history,
    privateIntel,
    selectedAccount,
    latestScores,
    refreshing,
    onRefresh,
}: {
    game: GameDetailsResponse;
    history: ScoreHistoryResponse | null;
    privateIntel: LatestPrivateIntelResponse | null;
    selectedAccount: PlanetsAccountResponse;
    latestScores: Map<number, ScoreHistoryItem>;
    refreshing: boolean;
    onRefresh: () => void;
}) {
    const [activeTab, setActiveTab] =
        useState<GameDashboardTab>("dashboard");

    const mySlot = privateIntel?.observer.player_slot_id ?? null;
    const myPlayer = mySlot === null
        ? null
        : game.players.find((item) => item.slot_id === mySlot) ?? null;

    const intelCounts = privateIntel?.counts ?? null;

    return (
        <section className="game-dashboard-shell">
            <nav
                className="game-dashboard-tabs"
                aria-label="Game dashboard sections"
            >
                {TABS.map((tab) => (
                    <button
                        className={activeTab === tab.id ? "is-active" : ""}
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        type="button"
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            <div className="game-dashboard-content">
                {activeTab === "dashboard" && (
                    <>
                        <section className="summary-grid game-dashboard-summary">
                            <button
                                className="summary-card"
                                onClick={() => setActiveTab("planets")}
                                type="button"
                            >
                                <span>Planets</span>
                                <strong>
                                    {myPlayer?.planets
                                        ?? intelCounts?.planets
                                        ?? "—"}
                                </strong>
                            </button>
                            <button
                                className="summary-card"
                                onClick={() => setActiveTab("starships")}
                                type="button"
                            >
                                <span>Starships</span>
                                <strong>
                                    {myPlayer?.ships
                                        ?? intelCounts?.ships
                                        ?? "—"}
                                </strong>
                            </button>
                            <button
                                className="summary-card"
                                onClick={() => setActiveTab("starbases")}
                                type="button"
                            >
                                <span>Starbases</span>
                                <strong>
                                    {myPlayer?.starbases
                                        ?? intelCounts?.starbases
                                        ?? "—"}
                                </strong>
                            </button>
                            <button
                                className="summary-card"
                                onClick={() => setActiveTab("scoreboard")}
                                type="button"
                            >
                                <span>Turn status</span>
                                <strong>
                                    {myPlayer?.turn_ready ? "Ready" : "Open"}
                                </strong>
                            </button>
                            <div className="summary-card">
                                <span>Schedule</span>
                                <strong>{game.schedule}</strong>
                            </div>
                            <div className="summary-card">
                                <span>Next host</span>
                                <strong>{game.time_to_host}</strong>
                            </div>
                        </section>

                        <section className="panel game-dashboard-home">
                            <div className="panel-header">
                                <div>
                                    <h2>{game.game.name}</h2>
                                    <p>
                                        Observer {selectedAccount.planets_username}
                                        {" · "}Turn {game.game.turn}
                                        {" · "}{game.game.status_name}
                                    </p>
                                </div>
                                <button
                                    className="secondary-button"
                                    disabled={refreshing}
                                    onClick={onRefresh}
                                    type="button"
                                >
                                    {refreshing ? "Syncing…" : "Refresh intel"}
                                </button>
                            </div>

                            <div className="game-dashboard-launch-grid">
                                {TABS.filter((tab) => tab.id !== "dashboard")
                                    .map((tab) => (
                                        <button
                                            key={tab.id}
                                            onClick={() => setActiveTab(tab.id)}
                                            type="button"
                                        >
                                            <strong>{tab.label}</strong>
                                            <small>Open section</small>
                                        </button>
                                    ))}
                            </div>
                        </section>
                    </>
                )}

                {activeTab === "vcr" && (
                    <VcrDashboardPanel
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        turn={game.game.turn}
                    />
                )}

                {activeTab === "reports" && (
                    <HostEventPanel
                        embedded
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        turn={game.game.turn}
                    />
                )}

                {activeTab === "planets" && (
                    <section className="panel">
                        <div className="panel-header">
                            <div>
                                <h2>Planet List</h2>
                                <p>
                                    {privateIntel?.planets.length ?? 0}
                                    {" factual planet observations for this observer."}
                                </p>
                            </div>
                        </div>
                        <div className="table-wrapper">
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr>
                                        <th>ID</th><th>Planet</th><th>Owner</th>
                                        <th>Colonists</th><th>Mines</th>
                                        <th>Factories</th><th>Defense</th>
                                        <th>Supplies</th><th>MC</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(privateIntel?.planets ?? []).map((planet) => {
                                        const facts = planetFacts(planet);
                                        return (
                                            <tr key={planet.planet_id}>
                                                <td>{planet.planet_id}</td>
                                                <td className="player-name">
                                                    {planet.name
                                                        ?? `Planet ${planet.planet_id}`}
                                                </td>
                                                <td>{playerName(game, planet.owner_id)}</td>
                                                <td>{formatInteger(facts.clans)}</td>
                                                <td>{formatInteger(facts.mines)}</td>
                                                <td>{formatInteger(facts.factories)}</td>
                                                <td>{formatInteger(facts.defense)}</td>
                                                <td>{formatInteger(facts.supplies)}</td>
                                                <td>{formatInteger(facts.megacredits)}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === "starships" && (
                    <StarshipListPanel
                        game={game}
                        intel={privateIntel}
                    />
                )}

                {activeTab === "starbases" && (
                    <StarbaseListPanel
                        game={game}
                        intel={privateIntel}
                    />
                )}

                {activeTab === "scoreboard" && (
                    <div className="game-dashboard-stack">
                        <PlayersTable
                            latestScores={latestScores}
                            players={game.players}
                        />
                        <PlayerActivityPanel
                            embedded
                            gameId={game.game.id}
                            throughTurn={game.game.turn}
                        />
                        {history !== null && (
                            <MilitaryScoreChart
                                history={history.items}
                                players={game.players}
                            />
                        )}
                    </div>
                )}

                {activeTab === "diplomacy" && (
                    <DiplomacyPanel
                        game={game}
                        observerSlotId={mySlot}
                    />
                )}

                {activeTab === "time-machine" && (
                    <TimeMachinePanel
                        currentTurn={game.game.turn}
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                    />
                )}

                {activeTab === "advantages" && (
                    <AdvantagesPanel
                        game={game}
                        observerSlotId={mySlot}
                    />
                )}

                {activeTab === "settings" && (
                    <div className="game-dashboard-stack">
                        <section className="panel">
                            <div className="panel-header">
                                <div>
                                    <h2>Game settings</h2>
                                    <p>
                                        Canonical game configuration. Client
                                        preferences and turn-order controls are
                                        separate from these rules.
                                    </p>
                                </div>
                                <button
                                    className="secondary-button"
                                    disabled={refreshing}
                                    onClick={onRefresh}
                                    type="button"
                                >
                                    {refreshing ? "Syncing…" : "Refresh private intel"}
                                </button>
                            </div>
                            <div className="game-dashboard-settings-grid">
                                {Object.entries(game.settings).map(([key, value]) => (
                                    <div key={key}>
                                        <span>{key.split("_").join(" ")}</span>
                                        <strong>
                                            {typeof value === "boolean"
                                                ? (value ? "Yes" : "No")
                                                : String(value)}
                                        </strong>
                                    </div>
                                ))}
                            </div>
                        </section>
                        <Placeholder title="Turn controls">
                            Full order entry, local order drafts, validation,
                            save/submit turn and upstream reconciliation belong
                            here once the write-path milestone is implemented.
                        </Placeholder>
                    </div>
                )}
            </div>
        </section>
    );
}
