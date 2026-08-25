import { useEffect, useMemo, useState } from "react";

import {
    getCombinedPrivateIntel,
    getGame,
} from "../../api/client";
import {
    getHistoricalCombatEvents,
    getHistoricalCombinedIntel,
    getHistoricalPrivateIntel,
} from "../../api/history";
import {
    getVcrReplayTrace,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";
import type { GameDetailsResponse } from "../../types/api";
import type {
    PrivateIntelMapResponse,
} from "../../types/intel";
import type {
    CombatEventSideSummary,
    CombatEventSummary,
} from "../../types/history";
import { BattlePlannerScenario } from "./BattlePlannerScenario";
import { StandaloneBattleSimulator } from "./StandaloneBattleSimulator";


function sideName(side: CombatEventSideSummary): string {
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}


function eventTitle(event: CombatEventSummary): string {
    return `${sideName(event.sides[0])} vs ${sideName(event.sides[1])}`;
}


export function BattlePlannerDashboardPanel({
    gameId,
    linkedAccountId,
    turn,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
}) {
    const [game, setGame] = useState<GameDetailsResponse | null>(null);
    const [intel, setIntel] = useState<PrivateIntelMapResponse | null>(null);
    const [contextLoading, setContextLoading] = useState(true);
    const [contextError, setContextError] = useState<string | null>(null);

    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [selectedVcrId, setSelectedVcrId] = useState<number | null>(null);
    const [trace, setTrace] = useState<VcrReplayTraceResponse | null>(null);
    const [loadingEvents, setLoadingEvents] = useState(true);
    const [loadingTrace, setLoadingTrace] = useState(false);
    const [vcrError, setVcrError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setContextLoading(true);
        setContextError(null);
        setGame(null);
        setIntel(null);

        void (async () => {
            try {
                const gameResponse = await getGame(gameId);
                if (cancelled) return;
                setGame(gameResponse);

                let intelResponse: PrivateIntelMapResponse | null = null;
                if (turn === gameResponse.game.turn) {
                    intelResponse = await getCombinedPrivateIntel(
                        gameId,
                        linkedAccountId,
                    );
                } else {
                    intelResponse = await getHistoricalCombinedIntel(
                        gameId,
                        linkedAccountId,
                        turn,
                    );
                    if (intelResponse === null) {
                        intelResponse = await getHistoricalPrivateIntel(
                            gameId,
                            linkedAccountId,
                            turn,
                        );
                    }
                }

                if (!cancelled) setIntel(intelResponse);
            } catch (reason) {
                if (!cancelled) {
                    setContextError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to prepare battle simulator intel context",
                    );
                }
            } finally {
                if (!cancelled) setContextLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    useEffect(() => {
        let cancelled = false;
        setLoadingEvents(true);
        setVcrError(null);
        setEvents([]);
        setSelectedVcrId(null);
        setTrace(null);

        void getHistoricalCombatEvents(gameId, linkedAccountId, turn)
            .then((response) => {
                if (cancelled) return;
                const ordered = [...response.events].sort(
                    (left, right) => left.vcr_id - right.vcr_id,
                );
                setEvents(ordered);
                setSelectedVcrId(ordered[0]?.vcr_id ?? null);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setVcrError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR validation sources",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoadingEvents(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    useEffect(() => {
        let cancelled = false;
        setTrace(null);

        if (selectedVcrId === null) {
            setLoadingTrace(false);
            return () => {
                cancelled = true;
            };
        }

        setLoadingTrace(true);
        void getVcrReplayTrace(gameId, linkedAccountId, turn, selectedVcrId)
            .then((response) => {
                if (!cancelled) setTrace(response);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setVcrError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to prepare factual VCR baseline",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoadingTrace(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, selectedVcrId, turn]);

    const selected = useMemo(
        () => events.find((event) => event.vcr_id === selectedVcrId) ?? null,
        [events, selectedVcrId],
    );

    return (
        <div style={{ display: "grid", gap: 16 }}>
            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">SIMULATION WORKBENCH · TURN {turn}</div>
                        <h2>Battle Simulator</h2>
                        <p>
                            Build future fights directly from known ship, planet and
                            starbase intel. Imported facts keep their evidence boundary;
                            unknown values remain explicit simulation assumptions.
                        </p>
                    </div>
                </div>

                {contextLoading ? (
                    <div className="loading-card">Loading known combatants…</div>
                ) : contextError !== null ? (
                    <div className="error-card">{contextError}</div>
                ) : game === null ? (
                    <div className="game-dashboard-empty">
                        Game combat context is unavailable.
                    </div>
                ) : (
                    <StandaloneBattleSimulator
                        game={game}
                        intel={intel}
                        turn={turn}
                    />
                )}
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">VCR-DERIVED VALIDATION LAB</div>
                        <h2>Replay-based scenarios</h2>
                        <p>
                            Optional secondary tool: start from one factual VCR and
                            change ammunition while keeping its exact combat setup.
                            This section is not required for standalone simulation.
                        </p>
                    </div>
                </div>

                {loadingEvents ? (
                    <div className="loading-card">Loading factual VCR baselines…</div>
                ) : events.length === 0 ? (
                    <div className="game-dashboard-empty">
                        No accessible VCRs are stored for turn {turn}. The standalone
                        simulator above remains available from known intel.
                    </div>
                ) : (
                    <div className="battle-planner-vcr-layout">
                        <aside className="battle-planner-vcr-baselines">
                            <div className="eyebrow">FACTUAL VCR BASELINES</div>
                            {events.map((event) => (
                                <button
                                    className={
                                        selectedVcrId === event.vcr_id
                                            ? "primary-button"
                                            : "secondary-button"
                                    }
                                    key={event.vcr_id}
                                    onClick={() => setSelectedVcrId(event.vcr_id)}
                                    style={{ textAlign: "left" }}
                                    type="button"
                                >
                                    <strong>VCR #{event.vcr_id}</strong>
                                    <span
                                        style={{
                                            display: "block",
                                            marginTop: 3,
                                            fontSize: 11,
                                            opacity: 0.9,
                                        }}
                                    >
                                        {eventTitle(event)}
                                    </span>
                                </button>
                            ))}
                        </aside>

                        <div className="battle-planner-vcr-detail">
                            {selected !== null && (
                                <div className="battle-planner-vcr-source">
                                    <div className="eyebrow">SOURCE VCR #{selected.vcr_id}</div>
                                    <h3 style={{ margin: "4px 0" }}>{eventTitle(selected)}</h3>
                                    <p style={{ margin: 0, color: "#91a9c8" }}>
                                        T{selected.turn}
                                        {selected.x !== null && selected.y !== null
                                            ? ` · ${selected.x}, ${selected.y}`
                                            : ""}
                                        {selected.sources.length > 0
                                            ? ` · observed via ${selected.sources.map((source) => source.planets_username).join(", ")}`
                                            : ""}
                                    </p>
                                </div>
                            )}

                            {vcrError !== null && (
                                <div className="error-card" style={{ marginBottom: 12 }}>
                                    {vcrError}
                                </div>
                            )}

                            {loadingTrace ? (
                                <div className="loading-card">Preparing deterministic baseline…</div>
                            ) : trace === null ? null : !trace.supported ? (
                                <div className="error-card">
                                    Exact NuHost replay is unavailable for this VCR: {trace.reason ?? "unsupported combat mode"}
                                </div>
                            ) : (
                                <BattlePlannerScenario
                                    factualTrace={trace}
                                    gameId={gameId}
                                    linkedAccountId={linkedAccountId}
                                    turn={turn}
                                    vcrId={trace.vcr_id}
                                />
                            )}
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}