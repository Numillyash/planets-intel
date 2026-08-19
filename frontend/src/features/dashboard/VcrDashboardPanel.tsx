import { useEffect, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import {
    getVcrReplayTrace,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";
import type {
    CombatEventSideSummary,
    CombatEventSummary,
} from "../../types/history";
import { CombatReplayPlayer } from "./CombatReplayPlayer";

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

export function VcrDashboardPanel({
    gameId,
    linkedAccountId,
    turn,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
}) {
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [trace, setTrace] = useState<VcrReplayTraceResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        void getHistoricalCombatEvents(gameId, linkedAccountId, turn)
            .then((response) => {
                if (cancelled) return;
                const ordered = [...response.events].sort(
                    (left, right) => left.vcr_id - right.vcr_id,
                );
                setEvents(ordered);
                setSelectedIndex(0);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR list",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    const selected = events[selectedIndex] ?? null;

    useEffect(() => {
        let cancelled = false;
        setTrace(null);

        if (selected === null) {
            return () => {
                cancelled = true;
            };
        }

        void getVcrReplayTrace(
            gameId,
            linkedAccountId,
            turn,
            selected.vcr_id,
        )
            .then((response) => {
                if (!cancelled) setTrace(response);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR playback trace",
                    );
                }
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, selected, turn]);

    return (
        <section className="panel vcr-dashboard-panel">
            <div className="panel-header">
                <div>
                    <h2>Visual Combat Replay</h2>
                    <p>
                        Interactive playback generated from the factual VCR
                        seed and the deterministic NuHost combat engine.
                    </p>
                </div>
            </div>

            {loading ? (
                <div className="loading-card">Loading VCRs…</div>
            ) : error !== null && events.length === 0 ? (
                <div className="error-card">{error}</div>
            ) : events.length === 0 ? (
                <div className="game-dashboard-empty">No VCRs for turn {turn}.</div>
            ) : (
                <div className="vcr-dashboard-layout">
                    <aside className="vcr-event-list">
                        {events.map((event, index) => (
                            <button
                                className={index === selectedIndex ? "is-active" : ""}
                                key={event.vcr_id}
                                onClick={() => setSelectedIndex(index)}
                                type="button"
                            >
                                <strong>VCR #{event.vcr_id}</strong>
                                <span>{eventTitle(event)}</span>
                            </button>
                        ))}
                    </aside>

                    <div className="vcr-dashboard-player-shell">
                        <div className="vcr-player-heading vcr-dashboard-player-heading">
                            <div>
                                <span>Turn {turn}</span>
                                <strong>
                                    {selected === null
                                        ? "VCR"
                                        : `VCR #${selected.vcr_id} · ${eventTitle(selected)}`}
                                </strong>
                            </div>
                            <div className="vcr-nav-buttons">
                                <button
                                    className="secondary-button"
                                    disabled={selectedIndex <= 0}
                                    onClick={() => setSelectedIndex((value) => value - 1)}
                                    type="button"
                                >
                                    Previous
                                </button>
                                <button
                                    className="secondary-button"
                                    disabled={selectedIndex >= events.length - 1}
                                    onClick={() => setSelectedIndex((value) => value + 1)}
                                    type="button"
                                >
                                    Next
                                </button>
                            </div>
                        </div>

                        {trace === null ? (
                            <div className="loading-card vcr-dashboard-player-state">
                                Preparing replay…
                            </div>
                        ) : !trace.supported ? (
                            <div className="error-card vcr-dashboard-player-state">
                                Exact visual replay unavailable: {trace.reason ?? "unsupported combat mode"}
                            </div>
                        ) : trace.frames.length === 0 ? (
                            <div className="error-card vcr-dashboard-player-state">
                                Replay contains no frames.
                            </div>
                        ) : (
                            <CombatReplayPlayer
                                autoPlay={false}
                                cycles={trace.cycles}
                                frames={trace.frames}
                                result={trace.result}
                            />
                        )}
                    </div>
                </div>
            )}
        </section>
    );
}
