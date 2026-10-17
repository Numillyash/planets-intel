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
import { PublicArchiveTimeMachine } from "./PublicArchiveTimeMachine";
import { DASHBOARD_TABS, GameDashboardTabs, GameDashboardOverview } from "./GameDashboardHome";
import type { PublicArchiveTurn } from "../../types/publicArchive";
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
    | "starmap"
    | "objects"
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

const TABS = DASHBOARD_TABS;

function dashboardTabFromRoute(value: string | null): GameDashboardTab {
    return value === "starmap" || value === "objects" || TABS.some((tab) => tab.id === value)
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
    publicMode = false,
    publicArchive = null,
    publicArchiveLoading = false,
    publicArchiveError = null,
    publicArchiveNotice = null,
    onOpenPublicTurn,
    onOpenPublicLatest,
}: {
    game: GameDetailsResponse;
    history: ScoreHistoryResponse | null;
    privateIntel: LatestPrivateIntelResponse | null;
    selectedAccount: PlanetsAccountResponse | null;
    publicMode?: boolean;
    publicArchive?: PublicArchiveTurn | null;
    publicArchiveLoading?: boolean;
    publicArchiveError?: string | null;
    publicArchiveNotice?: string | null;
    onOpenPublicTurn?: (slot: number, turn: number) => void;
    onOpenPublicLatest?: (slot: number) => void;
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
    const [publicObjectType, setPublicObjectType] = useState<"planets" | "starships" | "starbases">("planets");
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
    }, [game.game.id, selectedAccount?.id, publicMode]);

    useEffect(() => {
        const previous = previousCurrentTurn.current;
        if (dashboardTurn === previous && game.game.turn !== previous) {
            setDashboardTurn(game.game.turn);
        }
        previousCurrentTurn.current = game.game.turn;
    }, [dashboardTurn, game.game.turn]);

    useEffect(() => {
        let cancelled = false;

        if (publicMode || selectedAccount === null || dashboardTurn === game.game.turn) {
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
    }, [dashboardTurn, game.game.id, game.game.turn, selectedAccount?.id, publicMode]);

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

    // Shared game Dashboard layout, with source-gated read-only content.
    // No private observer token or local order hooks exist in this branch.
    if (publicMode) {
        const publicTab = TABS.some((t) => t.id === activeTab)
            ? activeTab : "dashboard";

        const publicScores = new Map<number, ScoreHistoryItem>();
        for (const item of history?.items ?? []) {
            if (item.turn === (publicArchive?.turn ?? game.game.turn)) {
                publicScores.set(item.slot_id, item);
            }
        }
        const observedCounts = publicArchive?.counts;
        const currentTurn = publicArchive?.turn ?? game.game.turn;
        const isFinished = game.game.status_id === 3;

        return (
            <section className="game-dashboard-shell public-archive-dashboard">
                <GameDashboardTabs activeTab={publicTab} onSelect={selectTab} />
                <div className="game-dashboard-content">
                    {publicArchiveLoading && (
                        <div className="public-archive-status" role="status">
                            Loading archived player perspective…
                        </div>
                    )}
                    {publicArchiveNotice !== null && (
                        <div className="public-archive-status" role="status">{publicArchiveNotice}</div>
                    )}
                    {publicArchiveError !== null && (
                        <div className="public-archive-status is-error" role="alert">{publicArchiveError}</div>
                    )}
                    {publicTab === "dashboard" && (
                        <GameDashboardOverview
                            game={game}
                            onSelect={selectTab}
                            summary={{
                                planets: observedCounts?.planets ?? "—",
                                ships: observedCounts?.ships ?? "—",
                                starbases: observedCounts?.starbases ?? "—",
                                turnState: publicArchive === null ? "—"
                                    : `Snapshot T${publicArchive.turn}`,
                                schedule: game.schedule || "—",
                                nextHost: isFinished ? "Finished" : game.time_to_host || "—",
                            }}
                            context={`Public archival perspective · slot #${publicArchive?.player_slot_id ?? "?"} · T${publicArchive?.turn ?? "?"} · ${game.game.status_name} · read-only (current schedule is public metadata)`}
                            action={<button type="button" className="secondary-button"
                                onClick={() => selectTab("time-machine")}>
                                {isFinished ? "Change historical turn" : "Time machine"}
                            </button>}
                        />
                    )}
                    {(publicTab === "objects" || publicTab === "planets" ||
                        publicTab === "starships" || publicTab === "starbases") && (
                        <section className="panel">
                            <div className="panel-header public-archive-objects-header">
                                <div>
                                    <h2>Historical objects · {publicArchive === null ? "unavailable" : `T${publicArchive.turn}`}</h2>
                                    <p>Observed data for the selected slot only; missing fields remain unknown.</p>
                                </div>
                                <label>Object type
                                    <select value={publicObjectType}
                                        onChange={(event) => setPublicObjectType(event.target.value as typeof publicObjectType)}>
                                        <option value="planets">Planets</option>
                                        <option value="starships">Starships</option>
                                        <option value="starbases">Starbases</option>
                                    </select>
                                </label>
                            </div>
                            {publicArchive === null ? (
                                <p className="public-archive-context">
                                    No archived entities loaded. Open an archived turn using Time machine.
                                </p>
                            ) : (
                                <div className="table-wrapper">
                                    <table className="players-table game-object-table">
                                        {publicObjectType === "planets" ? (
                                            <>
                                                <thead><tr><th>ID</th><th>Planet</th><th>Owner</th><th>Clans</th><th>MC</th></tr></thead>
                                                <tbody>{publicArchive.planets.map((p) => {
                                                    const facts = planetFacts(p);
                                                    return <tr key={p.planet_id}>
                                                        <td>{p.planet_id}</td>
                                                        <td>{p.name ?? "—"}</td>
                                                        <td>{playerName(game, p.owner_id)}</td>
                                                        <td>{formatInteger(facts.clans)}</td>
                                                        <td>{formatInteger(facts.megacredits)}</td>
                                                    </tr>;
                                                })}</tbody>
                                            </>
                                        ) : publicObjectType === "starships" ? (
                                            <>
                                                <thead><tr><th>ID</th><th>Ship</th><th>Owner</th><th>Hull</th><th>Warp</th></tr></thead>
                                                <tbody>{publicArchive.ships.map((ship) => (
                                                    <tr key={ship.ship_id}>
                                                        <td>{ship.ship_id}</td><td>{ship.name ?? "—"}</td>
                                                        <td>{playerName(game, ship.owner_id)}</td>
                                                        <td>{ship.hull_id ?? "—"}</td><td>{ship.warp ?? "—"}</td>
                                                    </tr>
                                                ))}</tbody>
                                            </>
                                        ) : (
                                            <>
                                                <thead><tr><th>ID</th><th>Planet</th><th>Race</th></tr></thead>
                                                <tbody>{publicArchive.starbases.map((base) => (
                                                    <tr key={base.starbase_id}>
                                                        <td>{base.starbase_id}</td><td>{base.planet_id ?? "—"}</td>
                                                        <td>{base.race_id ?? "—"}</td>
                                                    </tr>
                                                ))}</tbody>
                                            </>
                                        )}
                                    </table>
                                </div>
                            )}
                        </section>
                    )}
                    {publicTab === "scoreboard" && (
                        <div className="game-dashboard-stack">
                            <PlayersTable
                                latestScores={publicScores}
                                players={game.players}
                                snapshotTurn={publicArchive?.turn ?? null}
                            />
                            {history !== null && history.items.length > 0 && (
                                <MilitaryScoreChart history={history.items} players={game.players} />
                            )}
                            {history === null && (
                                <p className="muted">No stored public score history is available for this sector.</p>
                            )}
                        </div>
                    )}
                    {publicTab === "settings" && (
                        <section className="panel">
                            <div className="panel-header"><div>
                                <h2>Game settings</h2>
                                <p>Public current loadinfo settings; not a verified historical T{currentTurn} snapshot.</p>
                            </div></div>
                            <div className="game-dashboard-settings-grid">
                                {Object.entries(game.settings).map(([key, value]) => (
                                    <div key={key}>
                                        <span>{key.replaceAll("_", " ")}</span>
                                        <strong>{value === null ? "—" : String(value)}</strong>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}
                    {publicTab === "commander-intel" && (
                        <CommanderIntelligencePanel gameId={game.game.id} publicMode />
                    )}
                    {publicTab === "time-machine" && (
                        isFinished ? (
                            <PublicArchiveTimeMachine
                                key={game.game.id}
                                archive={publicArchive}
                                players={game.players}
                                finalTurn={game.game.turn}
                                loading={publicArchiveLoading}
                                error={publicArchiveError}
                                notice={publicArchiveNotice}
                                onOpenTurn={onOpenPublicTurn ?? (() => {})}
                                onOpenLatest={onOpenPublicLatest ?? (() => {})}
                            />
                        ) : (
                            <section className="panel game-dashboard-placeholder">
                                <h2>Time machine unavailable</h2>
                                <p>Historical private RST views become available after a public sector finishes.</p>
                            </section>
                        )
                    )}
                    {!["dashboard", "planets", "starships", "starbases",
                        "objects", "scoreboard", "settings", "commander-intel",
                        "time-machine"].includes(publicTab) && (
                        <section className="panel game-dashboard-placeholder">
                            <div className="eyebrow">Public historical mode · T{currentTurn}</div>
                            <h2>{TABS.find((tab) => tab.id === publicTab)?.label ?? "Section"}</h2>
                            <p>This section currently requires observer-specific or turn-indexed
                                evidence that is not included in the public archival RST.
                                No private account data is substituted.</p>
                        </section>
                    )}
                </div>
            </section>
        );
    }

    if (selectedAccount === null) {
        return <section className="panel"><p>Local observer is unavailable.</p></section>;
    }

    return (
        <section className="game-dashboard-shell">
            <GameDashboardTabs activeTab={activeTab} onSelect={selectTab} />

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
                    <GameDashboardOverview
                        game={game}
                        onSelect={selectTab}
                        summary={{
                            planets: historicalMode
                                ? intelCounts?.planets ?? "—"
                                : myPlayer?.planets ?? intelCounts?.planets ?? "—",
                            ships: historicalMode
                                ? intelCounts?.ships ?? "—"
                                : myPlayer?.ships ?? intelCounts?.ships ?? "—",
                            starbases: historicalMode
                                ? intelCounts?.starbases ?? "—"
                                : myPlayer?.starbases ?? intelCounts?.starbases ?? "—",
                            turnState: historicalMode ? `Snapshot T${dashboardTurn}`
                                : myPlayer?.turn_ready === null || myPlayer === null
                                    ? "—" : myPlayer.turn_ready ? "Ready" : "Open",
                            schedule: game.schedule || "—",
                            nextHost: game.time_to_host || "—",
                        }}
                        context={`Observer ${selectedAccount.planets_username} · Turn ${dashboardTurn} · ${historicalMode ? "historical snapshot" : game.game.status_name}${!historicalMode && game.source === "canonical-cache" ? " · cached game metadata" : ""}`}
                        action={historicalMode ? (
                            <button className="secondary-button" onClick={returnToLive} type="button">
                                Return to live
                            </button>
                        ) : (
                            <button className="secondary-button" disabled={refreshing}
                                onClick={onRefresh} type="button">
                                {refreshing ? "Syncing…" : "Refresh intel"}
                            </button>
                        )}
                    />
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
