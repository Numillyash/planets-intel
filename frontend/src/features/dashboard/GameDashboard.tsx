import { useMemo, useState } from "react";

import type {
    GameDetailsResponse,
    LatestPrivateIntelResponse,
    PlanetsAccountResponse,
    ScoreHistoryItem,
    ScoreHistoryResponse,
} from "../../types/api";
import { CombatEventPanel as VcrPanel } from "../map/CombatEventPanelLegacy";
import { HostEventPanel } from "../map/HostEventPanel";
import { PlayerActivityPanel } from "../map/PlayerActivityPanel";
import {
    formatInteger,
    planetFacts,
    shipFacts,
    starbaseFacts,
} from "../map/observationView";
import { PlayersTable } from "../players/PlayersTable";
import { MilitaryScoreChart } from "../statistics/MilitaryScoreChart";
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

function playerName(game: GameDetailsResponse, slotId: number | null): string {
    if (slotId === null || slotId <= 0) return "Unowned / unknown";
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} (slot ${slotId})` : `slot ${slotId}`;
}

function Placeholder({ title, children }: { title: string; children: string }) {
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
    const [activeTab, setActiveTab] = useState<GameDashboardTab>("dashboard");

    const availableHistoryTurns = useMemo(() => {
        if (history === null) return [];
        return [...new Set(history.items.map((item) => item.turn))]
            .sort((left, right) => right - left);
    }, [history]);

    const mySlot = privateIntel?.observer.player_slot_id ?? null;
    const myPlayer = mySlot === null
        ? null
        : game.players.find((item) => item.slot_id === mySlot) ?? null;

    const intelCounts = privateIntel?.counts ?? null;

    return (
        <section className="game-dashboard-shell">
            <nav className="game-dashboard-tabs" aria-label="Game dashboard sections">
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
                            <button className="summary-card" onClick={() => setActiveTab("planets")} type="button">
                                <span>Planets</span>
                                <strong>{myPlayer?.planets ?? intelCounts?.planets ?? "—"}</strong>
                            </button>
                            <button className="summary-card" onClick={() => setActiveTab("starships")} type="button">
                                <span>Starships</span>
                                <strong>{myPlayer?.ships ?? intelCounts?.ships ?? "—"}</strong>
                            </button>
                            <button className="summary-card" onClick={() => setActiveTab("starbases")} type="button">
                                <span>Starbases</span>
                                <strong>{myPlayer?.starbases ?? intelCounts?.starbases ?? "—"}</strong>
                            </button>
                            <button className="summary-card" onClick={() => setActiveTab("scoreboard")} type="button">
                                <span>Turn status</span>
                                <strong>{myPlayer?.turn_ready ? "Ready" : "Open"}</strong>
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
                                        Observer {selectedAccount.planets_username} · Turn {game.game.turn} · {game.game.status_name}
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
                                {TABS.filter((tab) => tab.id !== "dashboard").map((tab) => (
                                    <button key={tab.id} onClick={() => setActiveTab(tab.id)} type="button">
                                        <strong>{tab.label}</strong>
                                        <small>Open section</small>
                                    </button>
                                ))}
                            </div>
                        </section>
                    </>
                )}

                {activeTab === "vcr" && (
                    <section className="panel game-dashboard-legacy-embed">
                        <div className="panel-header">
                            <div>
                                <h2>Visual Combat Replay</h2>
                                <p>Factual VCR evidence plus derived post-combat state.</p>
                            </div>
                        </div>
                        <VcrPanel
                            gameId={game.game.id}
                            linkedAccountId={selectedAccount.id}
                            onFocus={() => undefined}
                            turn={game.game.turn}
                        />
                    </section>
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
                                <p>{privateIntel?.planets.length ?? 0} factual planet observations for this observer.</p>
                            </div>
                        </div>
                        <div className="table-wrapper">
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr>
                                        <th>ID</th><th>Planet</th><th>Owner</th><th>Colonists</th>
                                        <th>Mines</th><th>Factories</th><th>Defense</th><th>Supplies</th><th>MC</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(privateIntel?.planets ?? []).map((planet) => {
                                        const facts = planetFacts(planet);
                                        return (
                                            <tr key={planet.planet_id}>
                                                <td>{planet.planet_id}</td>
                                                <td className="player-name">{planet.name ?? `Planet ${planet.planet_id}`}</td>
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
                    <section className="panel">
                        <div className="panel-header">
                            <div>
                                <h2>Starship List</h2>
                                <p>{privateIntel?.ships.length ?? 0} factual ship observations for this observer.</p>
                            </div>
                        </div>
                        <div className="table-wrapper">
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr>
                                        <th>ID</th><th>Ship</th><th>Owner</th><th>Hull</th><th>Warp</th>
                                        <th>Fuel</th><th>Clans</th><th>Supplies</th><th>MC</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(privateIntel?.ships ?? []).map((ship) => {
                                        const facts = shipFacts(ship);
                                        return (
                                            <tr key={ship.ship_id}>
                                                <td>{ship.ship_id}</td>
                                                <td className="player-name">{ship.name ?? `Ship ${ship.ship_id}`}</td>
                                                <td>{playerName(game, ship.owner_id)}</td>
                                                <td>{facts.hullName ?? ship.hull_id ?? "—"}</td>
                                                <td>{ship.warp ?? "—"}</td>
                                                <td>{formatInteger(facts.fuel)}</td>
                                                <td>{formatInteger(facts.clans)}</td>
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

                {activeTab === "starbases" && (
                    <section className="panel">
                        <div className="panel-header">
                            <div>
                                <h2>Starbase List</h2>
                                <p>{privateIntel?.starbases.length ?? 0} factual starbase observations for this observer.</p>
                            </div>
                        </div>
                        <div className="table-wrapper">
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr>
                                        <th>ID</th><th>Planet</th><th>Defense</th><th>Fighters</th>
                                        <th>Beam tech</th><th>Engine tech</th><th>Hull tech</th><th>Torp tech</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(privateIntel?.starbases ?? []).map((base) => {
                                        const facts = starbaseFacts(base);
                                        const planet = privateIntel?.planets.find((item) => item.planet_id === base.planet_id);
                                        return (
                                            <tr key={base.starbase_id}>
                                                <td>{base.starbase_id}</td>
                                                <td className="player-name">{planet?.name ?? (base.planet_id !== null ? `Planet #${base.planet_id}` : "—")}</td>
                                                <td>{formatInteger(facts.defense)}</td>
                                                <td>{formatInteger(facts.fighters)}</td>
                                                <td>{facts.beamTech ?? "—"}</td>
                                                <td>{facts.engineTech ?? "—"}</td>
                                                <td>{facts.hullTech ?? "—"}</td>
                                                <td>{facts.torpedoTech ?? "—"}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === "scoreboard" && (
                    <div className="game-dashboard-stack">
                        <PlayersTable latestScores={latestScores} players={game.players} />
                        <PlayerActivityPanel embedded gameId={game.game.id} throughTurn={game.game.turn} />
                        {history !== null && (
                            <MilitaryScoreChart history={history.items} players={game.players} />
                        )}
                    </div>
                )}

                {activeTab === "diplomacy" && (
                    <section className="panel">
                        <div className="panel-header">
                            <div>
                                <h2>Diplomacy</h2>
                                <p>Canonical relation state currently stored for this game.</p>
                            </div>
                        </div>
                        <div className="table-wrapper">
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr><th>From</th><th>To</th><th>From status</th><th>To status</th><th>Conflict</th></tr>
                                </thead>
                                <tbody>
                                    {game.relations.map((relation) => (
                                        <tr key={relation.id}>
                                            <td>{playerName(game, relation.player_id)}</td>
                                            <td>{playerName(game, relation.player_to_id)}</td>
                                            <td>{relation.relation_from}</td>
                                            <td>{relation.relation_to}</td>
                                            <td>{relation.conflict_level}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}

                {activeTab === "time-machine" && (
                    <div className="game-dashboard-stack">
                        <section className="panel">
                            <div className="panel-header">
                                <div>
                                    <h2>Time machine</h2>
                                    <p>Stored public score history. Private per-entity turn browsing will be attached here.</p>
                                </div>
                            </div>
                            <div className="game-dashboard-turn-chips">
                                {availableHistoryTurns.length === 0
                                    ? <span>No historical turns stored.</span>
                                    : availableHistoryTurns.map((turn) => <span key={turn}>T{turn}</span>)}
                            </div>
                        </section>
                        {history !== null && (
                            <MilitaryScoreChart history={history.items} players={game.players} />
                        )}
                    </div>
                )}

                {activeTab === "advantages" && (
                    <Placeholder title="Advantages">
                        The game-rule catalog is already stored by the backend, but race/campaign advantages do not yet have a dedicated dashboard read model. This tab is reserved for that integration instead of inventing values.
                    </Placeholder>
                )}

                {activeTab === "settings" && (
                    <div className="game-dashboard-stack">
                        <section className="panel">
                            <div className="panel-header">
                                <div>
                                    <h2>Game settings</h2>
                                    <p>Canonical game configuration. Client preferences and turn-order controls will be separated from these rules.</p>
                                </div>
                                <button className="secondary-button" disabled={refreshing} onClick={onRefresh} type="button">
                                    {refreshing ? "Syncing…" : "Refresh private intel"}
                                </button>
                            </div>
                            <div className="game-dashboard-settings-grid">
                                {Object.entries(game.settings).map(([key, value]) => (
                                    <div key={key}>
                                        <span>{key.replaceAll("_", " ")}</span>
                                        <strong>{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</strong>
                                    </div>
                                ))}
                            </div>
                        </section>
                        <Placeholder title="Turn controls">
                            Full order entry, save/submit turn, client preferences and reset-turn semantics belong here once the write-path milestone is implemented.
                        </Placeholder>
                    </div>
                )}
            </div>
        </section>
    );
}
