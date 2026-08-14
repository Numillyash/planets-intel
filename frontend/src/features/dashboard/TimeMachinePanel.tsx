import { useEffect, useMemo, useState } from "react";

import {
    backfillHistoricalTurn,
    getHistoricalCombinedIntel,
    getHistoricalIntelStatus,
    getHistoricalPrivateIntel,
} from "../../api/history";
import type { HistoricalIntelStatus } from "../../types/history";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { planetFacts, shipFacts } from "../map/observationView";

function observerName(intel: PrivateIntelMapResponse): string {
    return isCombinedPrivateIntel(intel)
        ? intel.primary_observer.planets_username
        : intel.observer.planets_username;
}

export function TimeMachinePanel({
    gameId,
    linkedAccountId,
    currentTurn,
}: {
    gameId: number;
    linkedAccountId: number;
    currentTurn: number;
}) {
    const [status, setStatus] = useState<HistoricalIntelStatus | null>(null);
    const [selectedTurn, setSelectedTurn] = useState<number>(
        Math.max(1, currentTurn - 1),
    );
    const [intel, setIntel] = useState<PrivateIntelMapResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [backfilling, setBackfilling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function refreshStatus() {
        const response = await getHistoricalIntelStatus(
            gameId,
            linkedAccountId,
        );
        setStatus(response);
        return response;
    }

    useEffect(() => {
        let cancelled = false;
        setError(null);

        void refreshStatus()
            .then((response) => {
                if (cancelled) return;
                const candidates = response.complete_turns.length > 0
                    ? response.complete_turns
                    : response.available_turns;
                const preferred = [...candidates]
                    .filter((turn) => turn < currentTurn)
                    .sort((left, right) => right - left)[0];
                if (preferred !== undefined) setSelectedTurn(preferred);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load historical status",
                    );
                }
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, currentTurn]);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        setIntel(null);

        async function loadTurn() {
            try {
                const combined = await getHistoricalCombinedIntel(
                    gameId,
                    linkedAccountId,
                    selectedTurn,
                );
                if (cancelled) return;

                if (combined !== null) {
                    setIntel(combined);
                    return;
                }

                const single = await getHistoricalPrivateIntel(
                    gameId,
                    linkedAccountId,
                    selectedTurn,
                );
                if (!cancelled) setIntel(single);
            } catch (reason) {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load historical turn",
                    );
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        void loadTurn();
        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, selectedTurn]);

    const allTurns = useMemo(
        () => Array.from(
            { length: Math.max(0, currentTurn - 1) },
            (_item, index) => currentTurn - 1 - index,
        ),
        [currentTurn],
    );

    const complete = status?.complete_turns.includes(selectedTurn) ?? false;
    const available = status?.available_turns.includes(selectedTurn) ?? false;

    async function backfillSelected() {
        setBackfilling(true);
        setError(null);
        try {
            await backfillHistoricalTurn(
                gameId,
                linkedAccountId,
                selectedTurn,
            );
            await refreshStatus();

            const combined = await getHistoricalCombinedIntel(
                gameId,
                linkedAccountId,
                selectedTurn,
            );
            if (combined !== null) {
                setIntel(combined);
            } else {
                setIntel(
                    await getHistoricalPrivateIntel(
                        gameId,
                        linkedAccountId,
                        selectedTurn,
                    ),
                );
            }
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Historical backfill failed",
            );
        } finally {
            setBackfilling(false);
        }
    }

    return (
        <section className="panel time-machine-panel">
            <div className="panel-header">
                <div>
                    <h2>Time machine</h2>
                    <p>
                        Browse stored end-of-turn intelligence snapshots rather
                        than only public score history.
                    </p>
                </div>

                <div className="time-machine-controls">
                    <select
                        className="secondary-button"
                        onChange={(event) =>
                            setSelectedTurn(Number(event.target.value))
                        }
                        value={selectedTurn}
                    >
                        {allTurns.map((turn) => (
                            <option key={turn} value={turn}>
                                Turn {turn}
                                {status?.complete_turns.includes(turn)
                                    ? " · complete"
                                    : status?.available_turns.includes(turn)
                                      ? " · partial"
                                      : " · not stored"}
                            </option>
                        ))}
                    </select>

                    {!complete && (
                        <button
                            className="secondary-button"
                            disabled={backfilling}
                            onClick={() => void backfillSelected()}
                            type="button"
                        >
                            {backfilling
                                ? "Backfilling…"
                                : available
                                  ? "Complete backfill"
                                  : "Backfill turn"}
                        </button>
                    )}
                </div>
            </div>

            {error !== null && (
                <div className="auth-error" role="alert">{error}</div>
            )}

            {loading ? (
                <div className="loading-card">Loading turn {selectedTurn}…</div>
            ) : intel === null ? (
                <div className="game-dashboard-empty">
                    Turn {selectedTurn} is not stored yet. Use Backfill turn to
                    request it from Planets.nu.
                </div>
            ) : (
                <>
                    <div className="time-machine-summary">
                        <div><span>Turn</span><strong>{intel.turn}</strong></div>
                        <div><span>Observer</span><strong>{observerName(intel)}</strong></div>
                        <div><span>Planets</span><strong>{intel.counts.planets}</strong></div>
                        <div><span>Ships</span><strong>{intel.counts.ships}</strong></div>
                        <div><span>Starbases</span><strong>{intel.counts.starbases}</strong></div>
                        <div>
                            <span>Coverage</span>
                            <strong>{complete ? "Complete" : "Partial"}</strong>
                        </div>
                    </div>

                    <div className="time-machine-preview-grid">
                        <section>
                            <h3>Planets · T{selectedTurn}</h3>
                            <div className="time-machine-object-list">
                                {intel.planets.slice(0, 12).map((planet) => {
                                    const facts = planetFacts(planet);
                                    return (
                                        <div key={planet.planet_id}>
                                            <strong>
                                                #{planet.planet_id} {planet.name ?? "Unknown planet"}
                                            </strong>
                                            <small>
                                                owner {planet.owner_id ?? "?"} · clans {facts.clans ?? "?"}
                                            </small>
                                        </div>
                                    );
                                })}
                            </div>
                        </section>

                        <section>
                            <h3>Ships · T{selectedTurn}</h3>
                            <div className="time-machine-object-list">
                                {intel.ships.slice(0, 12).map((ship) => {
                                    const facts = shipFacts(ship);
                                    return (
                                        <div key={ship.ship_id}>
                                            <strong>
                                                #{ship.ship_id} {ship.name ?? "Unknown ship"}
                                            </strong>
                                            <small>
                                                owner {ship.owner_id ?? "?"} · warp {ship.warp ?? "?"} · fuel {facts.fuel ?? "?"}
                                            </small>
                                        </div>
                                    );
                                })}
                            </div>
                        </section>
                    </div>

                    <p className="time-machine-note">
                        This is historical factual/combined intelligence for the
                        selected turn. It does not overwrite the live map state.
                    </p>
                </>
            )}
        </section>
    );
}
