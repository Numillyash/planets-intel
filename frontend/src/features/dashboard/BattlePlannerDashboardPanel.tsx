import { useEffect, useMemo, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import {
    getVcrReplayTrace,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";
import type {
    CombatEventSideSummary,
    CombatEventSummary,
} from "../../types/history";
import { BattlePlannerScenario } from "./BattlePlannerScenario";


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
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [selectedVcrId, setSelectedVcrId] = useState<number | null>(null);
    const [trace, setTrace] = useState<VcrReplayTraceResponse | null>(null);
    const [loadingEvents, setLoadingEvents] = useState(true);
    const [loadingTrace, setLoadingTrace] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoadingEvents(true);
        setError(null);
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
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load battle planner VCR list",
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
        setError(null);

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
                    setError(
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
        <section className="panel">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">SIMULATION WORKBENCH · TURN {turn}</div>
                    <h2>Battle Planner</h2>
                    <p>
                        Start from one accessible factual VCR and test ammunition
                        assumptions with the deterministic NuHost combat engine.
                        Scenario results are derived and never persisted as intel facts.
                    </p>
                </div>
            </div>

            {loadingEvents ? (
                <div className="loading-card">Loading factual VCR baselines…</div>
            ) : error !== null && events.length === 0 ? (
                <div className="error-card">{error}</div>
            ) : events.length === 0 ? (
                <div className="game-dashboard-empty">
                    No accessible VCRs are stored for turn {turn}. Battle Planner needs
                    a factual VCR baseline in this MVP.
                </div>
            ) : (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(220px, 300px) minmax(0, 1fr)",
                        gap: 16,
                        alignItems: "start",
                    }}
                >
                    <aside style={{ display: "grid", gap: 7 }}>
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

                    <div style={{ minWidth: 0 }}>
                        {selected !== null && (
                            <div style={{ marginBottom: 12 }}>
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

                        {error !== null && events.length > 0 && (
                            <div className="error-card" style={{ marginBottom: 12 }}>
                                {error}
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
    );
}
