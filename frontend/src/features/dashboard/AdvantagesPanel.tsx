import { useEffect, useMemo, useState } from "react";

import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
import type { GameDetailsResponse } from "../../types/api";

function numericIds(value: unknown): number[] {
    if (Array.isArray(value)) {
        return value.flatMap((item) => numericIds(item));
    }
    if (typeof value === "number" && Number.isInteger(value)) {
        return value > 0 ? [value] : [];
    }
    if (typeof value === "string") {
        const matches = value.match(/\d+/g) ?? [];
        return matches
            .map((item) => Number(item))
            .filter((item) => Number.isInteger(item) && item > 0);
    }
    return [];
}

function recordId(record: Record<string, unknown>): number | null {
    const value = record.id;
    return typeof value === "number" && Number.isInteger(value)
        ? value
        : null;
}

function textField(
    record: Record<string, unknown>,
    ...keys: string[]
): string | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "string" && value.trim()) {
            return value.trim();
        }
    }
    return null;
}

function advantageIdsForRace(
    race: Record<string, unknown> | undefined,
): Set<number> {
    const result = new Set<number>();
    if (race === undefined) return result;

    for (const [key, value] of Object.entries(race)) {
        if (!key.toLowerCase().includes("advantage")) continue;
        for (const id of numericIds(value)) result.add(id);
    }
    return result;
}

export function AdvantagesPanel({
    game,
    observerSlotId,
}: {
    game: GameDetailsResponse;
    observerSlotId: number | null;
}) {
    const [catalog, setCatalog] =
        useState<GameRuleCatalogResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedSlot, setSelectedSlot] = useState<number | null>(
        observerSlotId,
    );

    useEffect(() => {
        setSelectedSlot(observerSlotId);
    }, [observerSlotId]);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        void getGameRuleCatalog(game.game.id)
            .then((response) => {
                if (!cancelled) setCatalog(response);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load game rule catalog",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [game.game.id]);

    const selectedPlayer = game.players.find(
        (player) => player.slot_id === selectedSlot,
    ) ?? null;

    const view = useMemo(() => {
        if (catalog === null || selectedPlayer === null) return null;

        const active = new Set(
            numericIds(selectedPlayer.active_advantages),
        );
        const race = catalog.races.find(
            (record) => recordId(record) === selectedPlayer.race_id,
        );
        const raceIds = advantageIdsForRace(race);

        const relevant = catalog.advantages
            .filter((record) => {
                const id = recordId(record);
                if (id === null) return false;
                return active.has(id) || raceIds.has(id);
            })
            .sort((left, right) => {
                const leftId = recordId(left) ?? 999999;
                const rightId = recordId(right) ?? 999999;
                const leftActive = active.has(leftId) ? 0 : 1;
                const rightActive = active.has(rightId) ? 0 : 1;
                return leftActive - rightActive || leftId - rightId;
            });

        return { active, race, raceIds, relevant };
    }, [catalog, selectedPlayer]);

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Advantages</h2>
                    <p>
                        Persisted Nu race/advantage catalog with the selected
                        player&apos;s active advantage IDs from loadinfo.
                    </p>
                </div>

                <select
                    className="secondary-button"
                    onChange={(event) =>
                        setSelectedSlot(Number(event.target.value))
                    }
                    value={selectedSlot ?? ""}
                >
                    {game.players.map((player) => (
                        <option
                            key={player.slot_id}
                            value={player.slot_id}
                        >
                            {player.username} · slot {player.slot_id}
                        </option>
                    ))}
                </select>
            </div>

            {loading ? (
                <div className="loading-card">Loading advantages…</div>
            ) : error !== null ? (
                <div className="error-card">{error}</div>
            ) : view === null || selectedPlayer === null ? (
                <div className="game-dashboard-empty">
                    No advantage context is available.
                </div>
            ) : (
                <>
                    <div className="advantages-summary">
                        <div>
                            <span>Player</span>
                            <strong>{selectedPlayer.username}</strong>
                        </div>
                        <div>
                            <span>Race</span>
                            <strong>
                                {textField(
                                    view.race ?? {},
                                    "name",
                                    "racename",
                                ) ?? `Race #${selectedPlayer.race_id}`}
                            </strong>
                        </div>
                        <div>
                            <span>Active IDs</span>
                            <strong>
                                {view.active.size > 0
                                    ? [...view.active].join(", ")
                                    : "None reported"}
                            </strong>
                        </div>
                        <div>
                            <span>Race advantage IDs</span>
                            <strong>
                                {view.raceIds.size > 0
                                    ? [...view.raceIds].join(", ")
                                    : "Not exposed by race record"}
                            </strong>
                        </div>
                        <div>
                            <span>Active hull IDs</span>
                            <strong>
                                {numericIds(selectedPlayer.active_hulls).join(", ")
                                    || "None reported"}
                            </strong>
                        </div>
                    </div>

                    <div className="advantage-grid">
                        {view.relevant.length === 0 ? (
                            <div className="game-dashboard-empty">
                                No race-scoped advantage records could be matched.
                                The raw active/race IDs above are still factual
                                and are not replaced with guessed names.
                            </div>
                        ) : view.relevant.map((record) => {
                            const id = recordId(record);
                            const isActive =
                                id !== null && view.active.has(id);
                            const name = textField(
                                record,
                                "name",
                                "displayname",
                            ) ?? (id === null ? "Advantage" : `Advantage #${id}`);
                            const description = textField(
                                record,
                                "description",
                                "desc",
                                "text",
                            );

                            return (
                                <article
                                    className={
                                        `advantage-card${isActive ? " is-active" : ""}`
                                    }
                                    key={id ?? name}
                                >
                                    <div>
                                        <strong>{name}</strong>
                                        <span>
                                            {isActive ? "Active" : "Race catalog"}
                                        </span>
                                    </div>
                                    {description !== null && (
                                        <p>{description}</p>
                                    )}
                                    {id !== null && <small>ID {id}</small>}
                                </article>
                            );
                        })}
                    </div>
                </>
            )}
        </section>
    );
}
