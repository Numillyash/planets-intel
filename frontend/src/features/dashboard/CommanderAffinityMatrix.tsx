import { useEffect, useMemo, useState, type ReactNode } from "react";

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
    const source = pair?.source_game ?? null;
    const sourceCount = source === null ? 0 : 1;
    if (metric === "games") {
        if (pair === undefined || pair.shared_games === null) {
            return {
                label: sourceCount ? "≥1" : "?",
                meaning: sourceCount
                    ? "Source sector confirmed; previous public history unavailable"
                    : "Public history unavailable — not zero games",
                grade: sourceCount ? "one" : "unknown",
                partial: sourceCount > 0,
            };
        }
        const total = pair.shared_games + sourceCount;
        return {
            label: String(total),
            meaning: source === null
                ? pair.shared_games + " previous shared games"
                : total + " recorded shared sectors = " +
                    pair.shared_games + " previous + 1 selected source sector",
            grade: grade(total),
            partial: false,
        };
    }

    if (pair === undefined) {
        return {
            label: "?",
            meaning: "Pair evidence unavailable",
            grade: "unknown",
            partial: false,
        };
    }
    const sourceKnown = source?.overlap_intervals.reduce(
        (sum, interval) => sum + interval.turn_count, 0,
    ) ?? 0;
    const known = pair.known_overlapping_turn_count + sourceKnown;
    const complete = pair.shared_games !== null
        && pair.overlap_reconstruction_complete
        && (source === null || source.overlap_status === "complete");

    if (complete) {
        const exact = (pair.overlapping_turn_count ?? 0) + sourceKnown;
        return {
            label: String(exact),
            meaning: exact + " exact overlapping turns" +
                (source === null ? " in prior sectors" : " including source sector"),
            grade: grade(exact),
            partial: false,
        };
    }

    if (known > 0) {
        return {
            label: "≥" + known,
            meaning: "At least " + known +
                " bounded overlapping turns; some participation evidence incomplete",
            grade: grade(known),
            partial: true,
        };
    }

    if (pair.shared_games === 0 && source === null) {
        return {
            label: "0",
            meaning: "No previous shared games in available public histories",
            grade: "none",
            partial: false,
        };
    }

    return {
        label: "?",
        meaning: "Shared sector(s) found but simultaneous turns unconfirmed",
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
    renderEvidence: (pair: CommanderPairSummary) => ReactNode;
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
        (pair) => pair.known_overlapping_turn_count > 0
            || (pair.source_game?.overlap_intervals.length ?? 0) > 0,
    ).length;

    return (
        <section className="panel commander-affinity-panel">
            <div className="panel-header commander-affinity-heading">
                <div>
                    <div className="eyebrow">Public-history evidence · source game #{gameId}</div>
                    <h2>Player Affinity / Previous Encounters</h2>
                    <p>
                        Counts include the selected sector when its public roster is
                        available; prior games are counted separately. A shared
                        sector does not establish a friendship or alliance.
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
                <div><strong>{connectedPairs.length}</strong><span>Pairs with previous shared games</span></div>
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
                                ? "Total shared sectors: previous history plus the selected source sector when publicly verifiable."
                                : "Reconstructed overlapping turns, including source sector when publicly verifiable."}
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
                                        <span>{commander.username}{commander.status !== 1 ? " †" : ""}</span>
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
                                        <strong>{rowPlayer.username}{rowPlayer.status !== 1 ? " †" : ""}</strong>
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
                <span>† = departed/inactive · ≥ = proven lower bound, not an exact total</span>
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
                                        : selectedPair.shared_games + " previous shared games" +
                                        (selectedPair.source_game ? " + selected source sector" : "") +
                                        "; " + cell(selectedPair, "overlap").meaning}
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
                Method: previous player-history intersection, plus independently
                attributable source-sector participation from public join/drop
                events and roster. No temporal overlap is assumed for replacements.
                Unknown periods remain unknown; no behavioral or alliance inference.
            </p>
        </section>
    );
}
