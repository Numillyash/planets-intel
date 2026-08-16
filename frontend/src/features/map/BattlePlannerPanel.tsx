import { useEffect, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import {
    getVcrReplayTrace,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";
import type { CombatEventSummary } from "../../types/history";
import { BattlePlannerScenario } from "../dashboard/BattlePlannerScenario";


function sideName(event: CombatEventSummary, index: 0 | 1): string {
    const side = event.sides[index];
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}


export function BattlePlannerPanel({
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
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        setTrace(null);

        void getHistoricalCombatEvents(gameId, linkedAccountId, turn)
            .then((response) => {
                if (cancelled) return;
                const ordered = [...response.events].sort(
                    (left, right) => left.vcr_id - right.vcr_id,
                );
                setEvents(ordered);
                setSelectedVcrId((current) =>
                    current !== null && ordered.some((event) => event.vcr_id === current)
                        ? current
                        : ordered[0]?.vcr_id ?? null,
                );
            })
            .catch((reason) => {
                if (cancelled) return;
                setEvents([]);
                setSelectedVcrId(null);
                setError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load VCRs for Battle Planner",
                );
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    useEffect(() => {
        let cancelled = false;
        setTrace(null);
        if (selectedVcrId === null) return () => {
            cancelled = true;
        };

        void getVcrReplayTrace(
            gameId,
            linkedAccountId,
            turn,
            selectedVcrId,
        )
            .then((response) => {
                if (!cancelled) {
                    setTrace(response);
                    setError(null);
                }
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load factual VCR baseline",
                    );
                }
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, selectedVcrId, turn]);

    return (
        <section className="panel dashboard-embedded-panel">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">DERIVED COMBAT SIMULATION</div>
                    <h2>Battle Planner</h2>
                    <p>
                        Clone a factual VCR into a read-only what-if scenario.
                        Simulation assumptions never overwrite observed combat or
                        current ship state.
                    </p>
                </div>
                {events.length > 0 && (
                    <label style={{ minWidth: 300 }}>
                        <small>Source factual VCR</small>
                        <select
                            className="secondary-button"
                            onChange={(event) =>
                                setSelectedVcrId(Number(event.target.value))
                            }
                            style={{ width: "100%" }}
                            value={selectedVcrId ?? ""}
                        >
                            {events.map((event) => (
                                <option key={event.vcr_id} value={event.vcr_id}>
                                    VCR #{event.vcr_id} · {sideName(event, 0)} vs {sideName(event, 1)}
                                </option>
                            ))}
                        </select>
                    </label>
                )}
            </div>

            {loading && <div className="loading-card">Loading combat evidence…</div>}
            {error !== null && <div className="error-card">{error}</div>}
            {!loading && error === null && events.length === 0 && (
                <div className="game-dashboard-empty">
                    No factual VCR is available for turn {turn}; there is no
                    evidence baseline to clone into a scenario.
                </div>
            )}

            {trace !== null && selectedVcrId !== null && (
                !trace.supported ? (
                    <div className="error-card">
                        This VCR cannot be used by the exact NuHost planner: {trace.reason}
                    </div>
                ) : (
                    <BattlePlannerScenario
                        factualTrace={trace}
                        gameId={gameId}
                        linkedAccountId={linkedAccountId}
                        turn={turn}
                        vcrId={selectedVcrId}
                    />
                )
            )}
        </section>
    );
}
