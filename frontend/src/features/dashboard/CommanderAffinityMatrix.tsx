import { useEffect, useMemo, useState } from "react";

import type {
    CommanderDossier,
    CommanderPairSummary,
} from "../../types/commanderIntelligence";

type AffinityMetric = "games" | "overlap";

function pairKey(left: string, right: string): string {
    return JSON.stringify(
        [left.trim().toLocaleLowerCase(), right.trim().toLocaleLowerCase()].sort(),
    );
}

function grade(count: number): string {
    if (count <= 0) return "none";
    if (count === 1) return "one";
    if (count === 2) return "two";
    if (count <= 4) return "medium";
    return "high";
}

function cell(
    pair: CommanderPairSummary | undefined,
    metric: AffinityMetric,
): { label: string; meaning: string; grade: string; partial: boolean } {
    if (pair === undefined || pair.shared_games === null) {
        return {
            label: "?",
            meaning: "Public history unavailable — not zero games",
            grade: "unknown",
            partial: false,
        };
    }

    if (metric === "games") {
        return {
            label: String(pair.shared_games),
            meaning: pair.shared_games + " other games in both public histories",
            grade: grade(pair.shared_games),
            partial: false,
        };
    }

    if (pair.overlap_reconstruction_complete && pair.overlapping_turn_count !== null) {
        return {
            label: String(pair.overlapping_turn_count),
            meaning: pair.overlapping_turn_count + " reconstructed overlapping turns",
            grade: grade(pair.overlapping_turn_count),
            partial: false,
        };
    }

    if (pair.shared_games === 0) {
        return {
            label: "0",
            meaning: "No other shared games in available public histories",
            grade: "none",
            partial: false,
        };
    }

    if (pair.known_overlapping_turn_count > 0) {
        return {
            label: "≥" + pair.known_overlapping_turn_count,
            meaning: "At least " + pair.known_overlapping_turn_count +
                " bounded overlapping turns; other intervals incomplete",
            grade: grade(pair.known_overlapping_turn_count),
            partial: true,
        };
    }

    return {
        label: "?",
        meaning: "Games shared, but actual overlapping turns unconfirmed",
        grade: "unknown",
        partial: false,
    };
}

export function CommanderAffinityMatrix({
    gameId,
    commanders,
    pairwise,
    renderEvidence,
}: {
    gameId: number;
    commanders: CommanderDossier[];
    pairwise: CommanderPairSummary[];
    renderEvidence: (pair: CommanderPairSummary) => React.ReactNode;
}) {
    const [metric, setMetric] = useState<AffinityMetric>("games");
    const [selectedKey, setSelectedKey] = useState<string | null>(null);
    const [onlyConnected, setOnlyConnected] = useState(false);

    useEffect(() => {
        setSelectedKey(null);
        setMetric("games");
        setOnlyConnected(false);
    }, [gameId]);

    const ordered = useMemo(
        () => [...commanders].sort((a, b) =>
            a.slot_id - b.slot_id ||
            a.username.localeCompare(b.username)),
        [commanders],
    );

    const byPair = useMemo(() => new Map(
        pairwise.map((pair) => [pairKey(pair.player_a, pair.player_b), pair]),
    ), [pairwise]);

    const connected = useMemo(() => new Set(
        pairwise
            .filter((pair) => pair.shared_games !== null && pair.shared_games > 0)
            .flatMap((pair) => [
                pair.player_a.trim().toLocaleLowerCase(),
                pair.player_b.trim().toLocaleLowerCase(),
            ]),
    ), [pairwise]);

    const visible = onlyConnected
        ? ordered.filter((item) => connected.has(item.username.trim().toLocaleLowerCase()))
        : ordered;

    const selectedPair = selectedKey === null ? null : byPair.get(selectedKey) ?? null;
    const knownPairs = pairwise.filter((pair) => pair.shared_games !== null);
    const connectedPairs = knownPairs.filter((pair) => (pair.shared_games ?? 0) > 0);
    const incompletePairs = pairwise.length - knownPairs.length;
    const confirmedOverlaps = pairwise.filter(
        (pair) => pair.known_overlapping_turn_count > 0,
    ).length;

    return (
        <section className="panel commander-affinity-panel">
            <div className="panel-header commander-affinity-heading">
                <div>
                    <div className="eyebrow">Public-history evidence · source game #{gameId}</div>
                    <h2>Player Affinity / Previous Encounters</h2>
                    <p>
                        Pairwise history of commanders in this sector, excluding the
                        current game. A past shared game is not evidence of an alliance.
                    </p>
                </div>
                <div className="commander-affinity-modes" role="group" aria-label="Matrix statistic">
                    <button
                        type="button"
                        className={metric === "games" ? "is-active" : ""}
                        aria-pressed={metric === "games"}
                        onClick={() => setMetric("games")}
                    >
                        Shared games
                    </button>
                    <button
                        type="button"
                        className={metric === "overlap" ? "is-active" : ""}
                        aria-pressed={metric === "overlap"}
                        onClick={() => setMetric("overlap")}
                    >
                        Overlapping turns
                    </button>
                </div>
            </div>

            <div className="commander-affinity-stats">
                <div><strong>{ordered.length}</strong><span>Commanders</span></div>
                <div><strong>{connectedPairs.length}</strong><span>Pairs with shared games</span></div>
                <div><strong>{confirmedOverlaps}</strong><span>Pairs with confirmed overlapping turns</span></div>
                <div><strong>{incompletePairs}</strong><span>Pairs with unavailable public history</span></div>
            </div>

            <label className="commander-affinity-filter">
                <input
                    type="checkbox"
                    checked={onlyConnected}
                    onChange={(event) => setOnlyConnected(event.target.checked)}
                />
                Show only commanders with a recorded prior encounter
            </label>

            {visible.length < 2 ? (
                <p className="muted">
                    {onlyConnected
                        ? "Fewer than two commanders have recorded prior shared games. Remove the filter to view all players."
                        : "At least two attributable human commanders are required."}
                </p>
            ) : (
                <div
                    className="commander-affinity-scroll"
                    role="region"
                    aria-label="Scrollable previous-encounters matrix"
                    tabIndex={0}
                >
                    <table className="commander-affinity-table">
                        <caption>
                            {metric === "games"
                                ? "Number of other games recorded in both players' public histories."
                                : "Turns both players were present together, when participation intervals are reconstructable."}
                            {" "}Choose a cell to inspect source games and participation evidence.
                        </caption>
                        <thead>
                            <tr>
                                <th scope="col" className="commander-affinity-corner">Player</th>
                                {visible.map((commander) => (
                                    <th
                                        scope="col"
                                        key={commander.username_normalized}
                                        title={commander.username}
                                    >
                                        <span>{commander.username}</span>
                                        <small>#{commander.slot_id}</small>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {visible.map((rowPlayer) => (
                                <tr key={rowPlayer.username_normalized}>
                                    <th
                                        scope="row"
                                        title={rowPlayer.username}
                                        className="commander-affinity-row-name"
                                    >
                                        <strong>{rowPlayer.username}</strong>
                                        <small>slot {rowPlayer.slot_id}</small>
                                    </th>
                                    {visible.map((columnPlayer) => {
                                        if (rowPlayer.username_normalized === columnPlayer.username_normalized) {
                                            return (
                                                <td
                                                    key={columnPlayer.username_normalized}
                                                    className="commander-affinity-diagonal"
                                                    aria-label={rowPlayer.username + " — same player"}
                                                >
                                                    —
                                                </td>
                                            );
                                        }
                                        const key = pairKey(rowPlayer.username, columnPlayer.username);
                                        const pair = byPair.get(key);
                                        const value = cell(pair, metric);
                                        const label = rowPlayer.username + " and " +
                                            columnPlayer.username + ": " + value.meaning;
                                        return (
                                            <td key={columnPlayer.username_normalized}>
                                                <button
                                                    type="button"
                                                    className={
                                                        "commander-affinity-cell commander-affinity-" +
                                                        value.grade + (value.partial ? " is-partial" : "") +
                                                        (selectedKey === key ? " is-selected" : "")
                                                    }
                                                    title={label}
                                                    aria-label={label + ". Open evidence."}
                                                    aria-pressed={selectedKey === key}
                                                    onClick={() => setSelectedKey(key)}
                                                >
                                                    {value.label}
                                                </button>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="commander-affinity-legend" aria-label="Matrix legend">
                <span>Number of shared games / turns:</span>
                <span><i className="commander-affinity-none" />0</span>
                <span><i className="commander-affinity-one" />1</span>
                <span><i className="commander-affinity-two" />2</span>
                <span><i className="commander-affinity-medium" />3–4</span>
                <span><i className="commander-affinity-high" />5+</span>
                <span><i className="commander-affinity-unknown" />unknown</span>
                <span>≥ indicates a proven lower bound, not an exact total</span>
            </div>

            <div className="commander-affinity-evidence" aria-live="polite">
                {selectedPair === null ? (
                    <p className="muted">
                        Select two different commanders to inspect their previous
                        shared sectors and exact/partial turn intersections.
                    </p>
                ) : (
                    <>
                        <div className="commander-affinity-evidence-title">
                            <div>
                                <div className="eyebrow">Selected pair · public evidence</div>
                                <h3>{selectedPair.player_a} ↔ {selectedPair.player_b}</h3>
                                <p className="muted">
                                    {selectedPair.shared_games === null
                                        ? "History unavailable — no conclusion about past encounters."
                                        : selectedPair.shared_games + " shared games; " +
                                        cell(selectedPair, "overlap").meaning}
                                </p>
                            </div>
                            <button
                                type="button"
                                className="secondary-button"
                                onClick={() => setSelectedKey(null)}
                            >
                                Clear selection
                            </button>
                        </div>
                        {renderEvidence(selectedPair)}
                    </>
                )}
            </div>
            <p className="commander-provenance">
                Method: exact player-history intersection, excluding this sector.
                Different usernames are treated as distinct accounts.
                Unknown participation intervals remain unknown; no behavioral
                conclusion or probability of alliance is inferred.
            </p>
        </section>
    );
}
