import { useCallback, useEffect, useMemo, useState } from "react";

import { getDraftMovementPrediction } from "../../api/movementPrediction";
import type { LatestPrivateIntelResponse } from "../../types/api";
import type {
    DraftMovementPredictionResponse,
    ShipMovementPrediction,
} from "../../types/movementPrediction";


function formatObservedAt(value: string): string {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
}


function formatCoordinate(x: number | null, y: number | null): string {
    if (x === null || y === null) return "—";
    return `${x}, ${y}`;
}


function predictionClass(item: ShipMovementPrediction): "PREDICTED" | "UNKNOWN" {
    return item.certain && item.predicted_x !== null && item.predicted_y !== null
        ? "PREDICTED"
        : "UNKNOWN";
}


function phaseLabel(item: ShipMovementPrediction): string {
    if (item.phase === "tow") {
        return item.tow_role === "target" ? "Tow · towed" : "Tow · tower";
    }
    if (item.phase === "move_most") return "Move Most";
    return "Intercept";
}


export function TurnReviewPanel({
    gameId,
    linkedAccountId,
    turn,
    intel,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    intel: LatestPrivateIntelResponse | null;
}) {
    const [prediction, setPrediction] =
        useState<DraftMovementPredictionResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [revision, setRevision] = useState(0);

    const load = useCallback(async () => {
        if (intel === null || intel.turn !== turn) {
            setPrediction(null);
            setLoading(false);
            setError(null);
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const response = await getDraftMovementPrediction(
                gameId,
                linkedAccountId,
                turn,
            );
            setPrediction(response);
        } catch (reason) {
            setPrediction(null);
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Movement prediction is unavailable",
            );
        } finally {
            setLoading(false);
        }
    }, [gameId, intel, linkedAccountId, turn]);

    useEffect(() => {
        void load();
    }, [load, revision]);

    useEffect(() => {
        const handleChanged = (event: Event) => {
            const detail = (event as CustomEvent<{
                gameId?: number;
                linkedAccountId?: number;
                turn?: number;
            }>).detail;
            if (
                detail?.gameId === gameId
                && detail?.linkedAccountId === linkedAccountId
                && detail?.turn === turn
            ) {
                setRevision((value) => value + 1);
            }
        };
        window.addEventListener("intel-order-drafts-changed", handleChanged);
        return () => {
            window.removeEventListener("intel-order-drafts-changed", handleChanged);
        };
    }, [gameId, linkedAccountId, turn]);

    const review = useMemo(() => {
        const items = prediction?.items ?? [];
        const predicted = items.filter(
            (item) => predictionClass(item) === "PREDICTED",
        );
        const unknown = items.length - predicted.length;
        const warnings = items.reduce(
            (total, item) => total + item.warnings.length,
            0,
        );
        const phases = new Map<string, number>();
        for (const item of items) {
            const label = phaseLabel(item);
            phases.set(label, (phases.get(label) ?? 0) + 1);
        }
        return {
            items,
            predicted: predicted.length,
            unknown,
            warnings,
            phases: [...phases.entries()],
        };
    }, [prediction]);

    return (
        <div className="game-dashboard-stack">
            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">Turn evidence ledger</div>
                        <h2>Turn Review · T{turn}</h2>
                        <p>
                            Facts, local planning state and derived movement predictions are
                            kept separate. Predictions are never promoted to factual Planets.nu state.
                        </p>
                    </div>
                    <button
                        className="secondary-button"
                        disabled={loading || intel === null}
                        onClick={() => void load()}
                        type="button"
                    >
                        {loading ? "Refreshing…" : "Refresh review"}
                    </button>
                </div>

                <div className="game-dashboard-settings-grid">
                    <div>
                        <span>Canonical turn</span>
                        <strong>T{turn}</strong>
                    </div>
                    <div>
                        <span>Factual private state</span>
                        <strong>
                            {intel === null
                                ? "UNAVAILABLE"
                                : intel.turn === turn
                                    ? `CURRENT FACT · T${intel.turn}`
                                    : `STALE FACT · T${intel.turn}`}
                        </strong>
                    </div>
                    <div>
                        <span>Observer</span>
                        <strong>{intel?.observer.planets_username ?? "—"}</strong>
                    </div>
                    <div>
                        <span>Observation batch</span>
                        <strong>{intel ? `#${intel.observation.batch_id}` : "—"}</strong>
                    </div>
                    <div>
                        <span>Fact source</span>
                        <strong>{intel?.observation.source ?? "—"}</strong>
                    </div>
                    <div>
                        <span>Observed at</span>
                        <strong>
                            {intel
                                ? formatObservedAt(intel.observation.observed_at)
                                : "—"}
                        </strong>
                    </div>
                </div>

                {intel === null && (
                    <div className="auth-error" role="alert" style={{ marginTop: 12 }}>
                        Current-turn private facts are unavailable or withheld because their
                        snapshot turn does not match the canonical game turn. Derived current-turn
                        movement output is therefore not shown.
                    </div>
                )}
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">Derived planning state</div>
                        <h2>Movement prediction</h2>
                        <p>
                            Backend basis: {prediction?.basis ?? "—"}. Host-final state: {" "}
                            {prediction === null ? "—" : prediction.host_final ? "yes" : "no"}.
                        </p>
                    </div>
                </div>

                {error !== null && (
                    <div className="auth-error" role="alert">{error}</div>
                )}

                {loading && prediction === null ? (
                    <div className="loading-card">Loading movement review…</div>
                ) : prediction === null ? (
                    <p>
                        No current prediction is available. This is UNKNOWN, not evidence that
                        no ship will move.
                    </p>
                ) : (
                    <>
                        <div className="summary-grid game-dashboard-summary">
                            <div className="summary-card">
                                <span>Predicted</span>
                                <strong>{review.predicted}</strong>
                            </div>
                            <div className="summary-card">
                                <span>Unknown / uncertain</span>
                                <strong>{review.unknown}</strong>
                            </div>
                            <div className="summary-card">
                                <span>Warnings</span>
                                <strong>{review.warnings}</strong>
                            </div>
                            <div className="summary-card">
                                <span>Intercept mode</span>
                                <strong>{prediction.intercept_mode}</strong>
                            </div>
                            {review.phases.map(([phase, count]) => (
                                <div className="summary-card" key={phase}>
                                    <span>{phase}</span>
                                    <strong>{count}</strong>
                                </div>
                            ))}
                        </div>

                        <div className="table-wrapper" style={{ marginTop: 12 }}>
                            <table className="players-table game-object-table">
                                <thead>
                                    <tr>
                                        <th>Ship</th>
                                        <th>Class</th>
                                        <th>Phase</th>
                                        <th>From</th>
                                        <th>Predicted</th>
                                        <th>Fuel</th>
                                        <th>Status / reason</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {review.items.map((item) => {
                                        const classification = predictionClass(item);
                                        return (
                                            <tr key={`${item.ship_id}:${item.phase}:${item.tow_role ?? "none"}`}>
                                                <td>#{item.ship_id}</td>
                                                <td>
                                                    <strong>{classification}</strong>
                                                </td>
                                                <td>{phaseLabel(item)}</td>
                                                <td>{formatCoordinate(item.start_x, item.start_y)}</td>
                                                <td>
                                                    {classification === "PREDICTED"
                                                        ? formatCoordinate(item.predicted_x, item.predicted_y)
                                                        : "—"}
                                                </td>
                                                <td>
                                                    {item.fuel_status}
                                                    {item.fuel_used !== null
                                                        ? ` · used ${item.fuel_used}`
                                                        : ""}
                                                </td>
                                                <td>
                                                    <strong>{item.status}</strong>
                                                    {item.reason ? ` · ${item.reason}` : ""}
                                                    {item.warnings.length > 0
                                                        ? ` · ${item.warnings.join("; ")}`
                                                        : ""}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </section>

            <section className="panel">
                <div className="eyebrow">Evidence classes</div>
                <h2>Interpretation contract</h2>
                <p>
                    <strong>CURRENT FACT</strong> is stored private observation evidence for T{turn}.
                    {" "}<strong>PREDICTED</strong> is deterministic derived output from the supported
                    movement model and current local planning inputs. <strong>UNKNOWN</strong> means the
                    model deliberately cannot produce a trustworthy endpoint. Local order drafts are
                    planning state and never overwrite factual observations.
                </p>
            </section>
        </div>
    );
}
