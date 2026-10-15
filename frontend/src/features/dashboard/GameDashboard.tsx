import { useEffect, useMemo, useRef, useState } from "react";

import {
    getHistoricalCombinedIntel,
    getHistoricalPrivateIntel,
} from "../../api/history";
import {
    readGameSurfaceRoute,
    subscribeGameSurfaceRoute,
    writeGameSurfaceRoute,
} from "../../lib/uiRouteState";
import type {
    GameDetailsResponse,
    LatestPrivateIntelResponse,
    PlanetsAccountResponse,
    ScoreHistoryItem,
    ScoreHistoryResponse,
} from "../../types/api";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { CommunicationsDashboardPanel } from "../map/CommunicationsDashboardPanel";
import { HostEventPanel } from "../map/HostEventPanel";
import { PlayerActivityPanel } from "../map/PlayerActivityPanel";
import {
    formatInteger,
    planetFacts,
} from "../map/observationView";
import { PlayersTable } from "../players/PlayersTable";
import { MilitaryScoreChart } from "../statistics/MilitaryScoreChart";
import { AdvantagesPanel } from "./AdvantagesPanel";
import { BattlePlannerDashboardPanel } from "./BattlePlannerDashboardPanel";
import { CombatFighterEvidencePanel } from "./CombatFighterEvidencePanel";
import { CommanderIntelligencePanel } from "./CommanderIntelligencePanel";
import { GameIntelGrantsPanel } from "./GameIntelGrantsPanel";
import { DiplomacyPanel } from "./DiplomacyPanel";
import { MilitaryAttributionPanel } from "./MilitaryAttributionPanel";
import { StarbaseListPanel } from "./StarbaseListPanel";
import { StarshipListPanel } from "./StarshipListPanel";
import { TimeMachinePanel } from "./TimeMachinePanel";
import { TurnReviewPanel } from "./TurnReviewPanel";
import { VcrDashboardPanel } from "./VcrDashboardPanel";
import "./game-dashboard.css";
import "./military-attribution.css";

type GameDashboardTab =
    | "dashboard"
    | "turn-review"
    | "vcr"
    | "battle-planner"
    | "reports"
    | "communications"
    | "commander-intel"
    | "planets"
    | "starships"
    | "starbases"
    | "scoreboard"
    | "military-intel"
    | "turn-timing"
    | "diplomacy"
    | "time-machine"
    | "advantages"
    | "settings";

const TABS: Array<{ id: GameDashboardTab; label: string }> = [
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
];

function dashboardTabFromRoute(value: string | null): GameDashboardTab {
    return TABS.some((tab) => tab.id === value)
        ? value as GameDashboardTab
        : "dashboard";
}

function playerName(
    game: GameDetailsResponse,
    slotId: number | null,
): string {
    if (slotId === null || slotId <= 0) return "Unowned / unknown";
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} (slot ${slotId})` : `slot ${slotId}`;
}

function observerSlot(intel: PrivateIntelMapResponse | null): number | null {
    if (intel === null) return null;
    return isCombinedPrivateIntel(intel)
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
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

function HistoricalUnavailable({
    title,
    turn,
    children,
}: {
    title: string;
    turn: number;
    children: string;
}) {
    return (
        <section className="panel game-dashboard-placeholder">
            <div className="eyebrow">Historical mode · T{turn}</div>
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
    const [activeTab, setActiveTab] = useState<GameDashboardTab>(() => {
        const route = readGameSurfaceRoute();
        return route.view === "dashboard"
            ? dashboardTabFromRoute(route.tab)
            : "dashboard";
    });
    const [dashboardTurn, setDashboardTurn] = useState(game.game.turn);
    const [historicalIntel, setHistoricalIntel] =
        useState<PrivateIntelMapResponse | null>(null);
    const [historicalLoading, setHistoricalLoading] = useState(false);
    const [historicalError, setHistoricalError] = useState<string | null>(null);
    const previousCurrentTurn = useRef(game.game.turn);

    function selectTab(tab: GameDashboardTab) {
        setActiveTab(tab);
        writeGameSurfaceRoute("dashboard", tab);
    }

    useEffect(() => subscribeGameSurfaceRoute(() => {
        const route = readGameSurfaceRoute();
        if (route.view === "dashboard") {
            setActiveTab(dashboardTabFromRoute(route.tab));
        }
    }), []);

    useEffect(() => {
        setDashboardTurn(game.game.turn);
        setHistoricalIntel(null);
        setHistoricalError(null);
    }, [game.game.id, selectedAccount.id]);

    useEffect(() => {
        const previous = previousCurrentTurn.current;
        if (dashboardTurn === previous && game.game.turn !== previous) {
            setDashboardTurn(game.game.turn);
        }
        previousCurrentTurn.current = game.game.turn;
    }, [dashboardTurn, game.game.turn]);

    useEffect(() => {
        let cancelled = false;

        if (dashboardTurn === game.game.turn) {
            setHistoricalIntel(null);
            setHistoricalLoading(false);
            setHistoricalError(null);
            return () => {
                cancelled = true;
            };
        }

        setHistoricalIntel(null);
        setHistoricalLoading(true);
        setHistoricalError(null);

        void (async () => {
            try {
                const combined = await getHistoricalCombinedIntel(
                    game.game.id,
                    selectedAccount.id,
                    dashboardTurn,
                );
                if (cancelled) return;
                if (combined !== null) {
                    setHistoricalIntel(combined);
                    return;
                }

                const single = await getHistoricalPrivateIntel(
                    game.game.id,
                    selectedAccount.id,
                    dashboardTurn,
                );
                if (!cancelled) {
                    setHistoricalIntel(single);
                    if (single === null) {
                        setHistoricalError(
                            `Turn ${dashboardTurn} has no stored private-intel snapshot.`,
                        );
                    }
                }
            } catch (reason) {
                if (!cancelled) {
                    setHistoricalError(
                        reason instanceof Error
                            ? reason.message
                            : `Failed to load turn ${dashboardTurn}`,
                    );
                }
            } finally {
                if (!cancelled) setHistoricalLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [dashboardTurn, game.game.id, game.game.turn, selectedAccount.id]);

    const historicalMode = dashboardTurn !== game.game.turn;
    const activeIntel: PrivateIntelMapResponse | null = historicalMode
        ? historicalIntel
        : privateIntel;
    const mySlot = observerSlot(activeIntel);
    const myPlayer = !historicalMode && mySlot !== null
        ? game.players.find((item) => item.slot_id === mySlot) ?? null
        : null;
    const intelCounts = activeIntel?.counts ?? null;

    const dashboardScores = useMemo(() => {
        if (!historicalMode) return latestScores;
        const scores = new Map<number, ScoreHistoryItem>();
        for (const item of history?.items ?? []) {
            if (item.turn === dashboardTurn) scores.set(item.slot_id, item);
        }
        return scores;
    }, [dashboardTurn, historicalMode, history, latestScores]);

    function returnToLive() {
        setDashboardTurn(game.game.turn);
        setHistoricalIntel(null);
        setHistoricalError(null);
    }

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
                        onClick={() => selectTab(tab.id)}
                        type="button"
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            {historicalMode && (
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 12,
                        margin: "10px 0 0",
                        padding: "9px 12px",
                        border: "1px solid rgba(255, 204, 115, 0.55)",
                        borderRadius: 8,
                        background: "rgba(75, 61, 32, 0.34)",
                    }}
                >
                    <div>
                        <strong>Historical mode · Turn {dashboardTurn}</strong>
                        <div style={{ color: "#aabbd1", fontSize: 11, marginTop: 2 }}>
                            Turn-aware sections use stored T{dashboardTurn} evidence.
                            Current-only metadata is not substituted as historical state.
                        </div>
                    </div>
                    <button
                        className="secondary-button"
                        onClick={returnToLive}
                        type="button"
                    >
                        Return to live · T{game.game.turn}
                    </button>
                </div>
            )}

            {historicalLoading && (
                <div className="loading-card">Loading historical turn {dashboardTurn}…</div>
            )}
            {historicalError !== null && (
                <div className="auth-error" role="alert">{historicalError}</div>
            )}

            <div className="game-dashboard-content">
                {activeTab === "dashboard" && (
                    <>
                        <section className="summary-grid game-dashboard-summary">
                            <button className="summary-card" onClick={() => selectTab("planets")} type="button">
                                <span>Planets</span>
                                <strong>
                                    {historicalMode
                                        ? intelCounts?.planets ?? "—"
                                        : myPlayer?.planets ?? intelCounts?.planets ?? "—"}
                                </strong>
                            </button>
                            <button className="summary-card" onClick={() => selectTab("starships")} type="button">
                                <span>Starships</span>
                                <strong>
                                    {historicalMode
                                        ? intelCounts?.ships ?? "—"
                                        : myPlayer?.ships ?? intelCounts?.ships ?? "—"}
                                </strong>
                            </button>
                            <button className="summary-card" onClick={() => selectTab("starbases")} type="button">
                                <span>Starbases</span>
                                <strong>
                                    {historicalMode
                                        ? intelCounts?.starbases ?? "—"
                                        : myPlayer?.starbases ?? intelCounts?.starbases ?? "—"}
                                </strong>
                            </button>
                            <button className="summary-card" onClick={() => selectTab("scoreboard")} type="button">
                                <span>Turn state</span>
                                <strong>
                                    {historicalMode
                                        ? `Snapshot T${dashboardTurn}`
                                        : myPlayer?.turn_ready === null || myPlayer === null
                                            ? "—"
                                            : myPlayer.turn_ready ? "Ready" : "Open"}
                                </strong>
                            </button>
                            <div className="summary-card">
                                <span>{historicalMode ? "Live schedule" : "Schedule"}</span>
                                <strong>{game.schedule || "—"}</strong>
                            </div>
                            <div className="summary-card">
                                <span>{historicalMode ? "Live next host" : "Next host"}</span>
                                <strong>{game.time_to_host || "—"}</strong>
                            </div>
                        </section>

                        <section className="panel game-dashboard-home">
                            <div className="panel-header">
                                <div>
                                    <h2>{game.game.name}</h2>
                                    <p>
                                        Observer {selectedAccount.planets_username}
                                        {" · "}Turn {dashboardTurn}
                                        {historicalMode ? " · historical snapshot" : ` · ${game.game.status_name}`}
                                        {!historicalMode && game.source === "canonical-cache"
                                            ? " · cached game metadata"
                                            : ""}
                                    </p>
                                </div>
                                {historicalMode ? (
                                    <button className="secondary-button" onClick={returnToLive} type="button">
                                        Return to live
                                    </button>
                                ) : (
                                    <button className="secondary-button" disabled={refreshing} onClick={onRefresh} type="button">
                                        {refreshing ? "Syncing…" : "Refresh intel"}
                                    </button>
                                )}
                            </div>

                            <div className="game-dashboard-launch-grid">
                                {TABS.filter((tab) => tab.id !== "dashboard").map((tab) => (
                                    <button key={tab.id} onClick={() => selectTab(tab.id)} type="button">
                                        <strong>{tab.label}</strong>
                                        <small>Open section</small>
                                    </button>
                                ))}
                            </div>
                        </section>
                    </>
                )}

                {activeTab === "turn-review" && (
                    historicalMode ? (
                        <HistoricalUnavailable title="Turn Review is a current planning surface" turn={dashboardTurn}>
                            Historical snapshots remain factual evidence. Current local drafts and
                            derived movement predictions are intentionally not projected backward
                            onto a historical turn.
                        </HistoricalUnavailable>
                    ) : (
                        <TurnReviewPanel
                            gameId={game.game.id}
                            intel={privateIntel}
                            linkedAccountId={selectedAccount.id}
                            turn={dashboardTurn}
                        />
                    )
                )}

                {activeTab === "vcr" && (
                    <VcrDashboardPanel
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        turn={dashboardTurn}
                    />
                )}

                {activeTab === "battle-planner" && (
                    <BattlePlannerDashboardPanel
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        turn={dashboardTurn}
                    />
                )}

                {activeTab === "reports" && (
                    <HostEventPanel
                        embedded
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        turn={dashboardTurn}
                    />
                )}

                {activeTab === "communications" && (
                    historicalMode ? (
                        <HistoricalUnavailable title="Historical communications view unavailable" turn={dashboardTurn}>
                            Communications are stored as the current observer feed, not as a
                            turn-indexed snapshot. Live messages are hidden in historical mode.
                        </HistoricalUnavailable>
                    ) : (
                        <CommunicationsDashboardPanel
                            gameId={game.game.id}
                            linkedAccountId={selectedAccount.id}
                        />
                    )
                )}

                {activeTab === "commander-intel" && (
                    historicalMode ? (
                        <HistoricalUnavailable
                            title="Commander Intelligence is a live-roster view"
                            turn={dashboardTurn}
                        >
                            The dossier is anchored to the canonical current-game
                            commander roster and public historical game records.
                            It is intentionally not relabelled as a turn-indexed
                            Time Machine snapshot.
                        </HistoricalUnavailable>
                    ) : (
                        <CommanderIntelligencePanel gameId={game.game.id} />
                    )
                )}

                {activeTab === "planets" && (
                    <section className="panel">
                        <div className="panel-header">
                            <div>
                                <h2>Planet List · T{dashboardTurn}</h2>
                                <p>{activeIntel?.planets.length ?? 0}{" factual planet observations for this snapshot."}</p>
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
                                    {(activeIntel?.planets ?? []).map((planet) => {
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

                {activeTab === "starships" && <StarshipListPanel game={game} intel={activeIntel} />}
                {activeTab === "starbases" && <StarbaseListPanel game={game} intel={activeIntel} />}

                {activeTab === "scoreboard" && (
                    <div className="game-dashboard-stack">
                        <PlayersTable
                            latestScores={dashboardScores}
                            players={game.players}
                            snapshotTurn={historicalMode ? dashboardTurn : null}
                        />
                        {history !== null && (
                            <MilitaryScoreChart history={history.items} players={game.players} />
                        )}
                    </div>
                )}

                {activeTab === "military-intel" && (
                    <div className="game-dashboard-stack">
                        {history !== null && (
                            <MilitaryAttributionPanel
                                game={game}
                                history={history}
                                linkedAccountId={selectedAccount.id}
                            />
                        )}
                        <CombatFighterEvidencePanel
                            game={game}
                            linkedAccountId={selectedAccount.id}
                            turn={dashboardTurn}
                        />
                    </div>
                )}

                {activeTab === "turn-timing" && (
                    <PlayerActivityPanel embedded gameId={game.game.id} throughTurn={dashboardTurn} />
                )}

                {activeTab === "diplomacy" && (
                    historicalMode ? (
                        <HistoricalUnavailable title="Historical diplomacy snapshot unavailable" turn={dashboardTurn}>
                            Relations are currently stored as canonical live game metadata,
                            not as turn-indexed factual snapshots. Showing today's relations
                            here would falsely label current state as historical evidence.
                        </HistoricalUnavailable>
                    ) : (
                        <DiplomacyPanel game={game} observerSlotId={mySlot} />
                    )
                )}

                {activeTab === "time-machine" && (
                    <TimeMachinePanel
                        activeTurn={dashboardTurn}
                        currentTurn={game.game.turn}
                        gameId={game.game.id}
                        linkedAccountId={selectedAccount.id}
                        onOpenTurn={(turn) => {
                            setDashboardTurn(turn);
                            selectTab("dashboard");
                        }}
                    />
                )}

                {activeTab === "advantages" && (
                    historicalMode ? (
                        <HistoricalUnavailable title="Historical advantages snapshot unavailable" turn={dashboardTurn}>
                            Player advantage activation is not yet persisted as a
                            turn-indexed snapshot. The live advantage set is intentionally
                            hidden while browsing a historical turn.
                        </HistoricalUnavailable>
                    ) : (
                        <AdvantagesPanel game={game} observerSlotId={mySlot} />
                    )
                )}

                {activeTab === "settings" && (
                    historicalMode ? (
                        <HistoricalUnavailable title="Historical game-settings snapshot unavailable" turn={dashboardTurn}>
                            The current canonical game settings are not evidence that the
                            same mutable settings were active on this historical turn.
                        </HistoricalUnavailable>
                    ) : (
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
                                                {value === null
                                                    ? "—"
                                                    : typeof value === "boolean"
                                                        ? (value ? "Yes" : "No")
                                                        : String(value)}
                                            </strong>
                                        </div>
                                    ))}
                                </div>
                            </section>
                            <GameIntelGrantsPanel
                                gameId={game.game.id}
                                linkedAccountId={selectedAccount.id}
                            />
                            <Placeholder title="Turn controls">
                                Full order entry, local order drafts, validation,
                                save/submit turn and upstream reconciliation belong
                                here once the write-path milestone is implemented.
                            </Placeholder>
                        </div>
                    )
                )}
            </div>
        </section>
    );
}
