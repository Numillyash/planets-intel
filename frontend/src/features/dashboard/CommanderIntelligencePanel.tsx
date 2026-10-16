import { useEffect, useMemo, useState } from "react";

import { getCommanderIntelligence, getPublicCommanderIntelligence } from "../../api/commanderIntelligence";
import { CommanderAffinityMatrix } from "./CommanderAffinityMatrix";
import { raceName } from "../../lib/races";
import type {
    CommanderDossier,
    CommanderPairGame,
    CommanderPairSummary,
    CommanderParticipationInterval,
    CommanderRaceHistoryItem,
} from "../../types/commanderIntelligence";
import "./commander-intelligence.css";


function turnRange(interval: CommanderParticipationInterval): string {
    const start = interval.turn_from === null ? "?" : String(interval.turn_from);
    const end = interval.turn_to === null ? "?" : String(interval.turn_to);
    return "T" + start + "–" + end;
}


function exactOrLowerBound(
    exact: number | null,
    known: number,
): string {
    return exact === null ? "≥ " + known : exact.toLocaleString();
}


function raceLabel(item: CommanderRaceHistoryItem): string {
    if (item.race_name !== null && item.race_name.trim()) return item.race_name;
    if (item.race_id !== null) return raceName(item.race_id);
    return "Unknown race";
}


function PairGameEvidence({
    game,
    pair,
    isSource = false,
}: {
    game: CommanderPairGame;
    pair: CommanderPairSummary;
    isSource?: boolean;
}) {
    return (
        <details className="commander-game-evidence" key={game.game_id}>
            <summary>
                <span className="commander-game-title">
                    <strong>{game.name}</strong>
                    <small>#{game.game_id} · {game.status_name || "status " + game.status_id}
                        {isSource ? " · selected source sector" : ""}
                    </small>
                </span>
                <span className="commander-game-summary-actions">
                    <span className="commander-overlap-chip">
                        {game.overlap_status === "complete"
                            ? String(game.overlapping_turn_count ?? 0) + " overlapping turns"
                            : game.overlap_intervals.length > 0
                                ? "≥ " + game.overlap_intervals.reduce((sum, item) => sum + item.turn_count, 0) + " known turns"
                                : "overlap unknown"}
                    </span>
                    <a
                        className="commander-game-open-link"
                        href={`/intelboard/public/${game.game_id}`}
                        onClick={(event) => event.stopPropagation()}
                        title="Open this public sector in IntelBoard"
                    >
                        Open here <span aria-hidden="true">↗</span>
                    </a>
                    <a
                        className="commander-game-open-link is-external"
                        href={`https://planets.nu/#/sector/${game.game_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(event) => event.stopPropagation()}
                        title="Open this game on Planets.nu in a new tab"
                    >
                        Planets.nu <span aria-hidden="true">↗</span>
                    </a>
                </span>
            </summary>
            <div className="commander-evidence-grid">
                <div>
                    <strong>{pair.player_a}</strong>
                    {game.player_a_intervals.length === 0 ? (
                        <small>No attributable interval</small>
                    ) : game.player_a_intervals.map((interval, index) => (
                        <small key={"a-" + index}>
                            {turnRange(interval)}
                            {interval.slot_id === null ? "" : " · slot " + interval.slot_id}
                            {" · " + interval.reconstruction_quality}
                        </small>
                    ))}
                </div>
                <div>
                    <strong>{pair.player_b}</strong>
                    {game.player_b_intervals.length === 0 ? (
                        <small>No attributable interval</small>
                    ) : game.player_b_intervals.map((interval, index) => (
                        <small key={"b-" + index}>
                            {turnRange(interval)}
                            {interval.slot_id === null ? "" : " · slot " + interval.slot_id}
                            {" · " + interval.reconstruction_quality}
                        </small>
                    ))}
                </div>
                <div>
                    <strong>Exact intersection</strong>
                    {game.overlap_intervals.length === 0 ? (
                        <small>
                            {game.overlap_status === "complete"
                                ? "No overlapping bounded turns"
                                : "UNKNOWN — interval bounds incomplete"}
                        </small>
                    ) : game.overlap_intervals.map((interval, index) => (
                        <small key={"o-" + index}>
                            T{interval.turn_from}–{interval.turn_to}
                            {" · " + interval.turn_count + " turns"}
                        </small>
                    ))}
                </div>
            </div>
            <p className="commander-provenance">
                {game.provenance.source} · {game.provenance.cache_state}
                {game.provenance.fetched_at === null
                    ? ""
                    : " · fetched " + game.provenance.fetched_at}
            </p>
        </details>
    );
}

function PairDetails({ pair }: { pair: CommanderPairSummary }) {
    const sourceGame = pair.source_game ?? null;
    return (
        <div className="commander-pair-games">
            {sourceGame !== null && (
                <section className="commander-game-group">
                    <h4>Selected source sector · counted separately from previous games</h4>
                    <PairGameEvidence game={sourceGame} pair={pair} isSource />
                </section>
            )}
            {pair.shared_games === null ? (
                <p className="muted">
                    Previous public history unavailable for one or both players;
                    no zero-encounter claim is made.
                </p>
            ) : pair.games.length === 0 ? (
                <p className="muted">No previous shared running/finished games in available history.</p>
            ) : (
                <section className="commander-game-group">
                    <h4>Other shared sectors · {pair.shared_games} recorded</h4>
                    {pair.games.map((game) => (
                        <PairGameEvidence key={game.game_id} game={game} pair={pair} />
                    ))}
                </section>
            )}
        </div>
    );
}

export function CommanderIntelligencePanel({
    gameId,
    publicMode = false,
}: {
    gameId: number;
    publicMode?: boolean;
}) {
    const [data, setData] = useState<Awaited<ReturnType<typeof getCommanderIntelligence>> | null>(null);
    const [selected, setSelected] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        setData(null);

        void (publicMode ? getPublicCommanderIntelligence(gameId) : getCommanderIntelligence(gameId))
            .then((result) => {
                if (cancelled) return;
                setData(result);
                setSelected((current) => (
                    current !== null
                    && result.commanders.some((item) => item.username === current)
                        ? current
                        : result.commanders[0]?.username ?? null
                ));
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Commander intelligence failed",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, publicMode]);

    const dossier: CommanderDossier | null = useMemo(
        () => data?.commanders.find((item) => item.username === selected) ?? null,
        [data, selected],
    );

    const pairs = useMemo(
        () => (
            data?.pairwise
                .filter((item) =>
                    item.player_a === selected || item.player_b === selected)
                .sort((left, right) =>
                    (right.shared_games ?? -1) - (left.shared_games ?? -1))
            ?? []
        ),
        [data, selected],
    );

    const raceSummary = useMemo(() => {
        if (dossier === null) return [];
        const byRace = new Map<string, Set<number>>();
        for (const item of dossier.race_history) {
            const label = raceLabel(item);
            const games = byRace.get(label) ?? new Set<number>();
            games.add(item.game_id);
            byRace.set(label, games);
        }
        return [...byRace.entries()]
            .map(([label, games]) => ({ label, games: games.size }))
            .sort((a, b) => b.games - a.games || a.label.localeCompare(b.label));
    }, [dossier]);

    if (loading) {
        return (
            <section className="panel">
                <div className="panel-header">
                    <div>
                        <h2>Commander Intelligence</h2>
                        <p>Loading cached public Planets.nu history…</p>
                    </div>
                </div>
            </section>
        );
    }

    if (error !== null) {
        return (
            <section className="panel">
                <div className="error-box">{error}</div>
            </section>
        );
    }

    if (data === null || dossier === null) {
        return (
            <section className="panel">
                <p className="muted">No attributable active human commanders.</p>
            </section>
        );
    }

    return (
        <div className="game-dashboard-stack">
            <CommanderAffinityMatrix
                gameId={gameId}
                commanders={data.commanders}
                pairwise={data.pairwise}
                renderEvidence={(pair) => <PairDetails pair={pair} />}
            />
            <section className="panel commander-intel-panel">
                <div className="panel-header commander-header">
                    <div>
                        <div className="eyebrow">Derived historical summary · {data.method_version}</div>
                        <h2>Commander / Player Dossier</h2>
                        {publicMode && <p>Public sector #{gameId} · no linked observer or private intel</p>}
                        <p>
                            Public game history with replacement-aware participation.
                            Co-presence is not interpreted as alliance, rivalry or coordination.
                        </p>
                    </div>
                    <select
                        value={dossier.username}
                        onChange={(event) => setSelected(event.target.value)}
                    >
                        {data.commanders.map((item) => (
                            <option key={item.username_normalized} value={item.username}>
                                {item.username} · slot {item.slot_id} · {raceName(item.race_id)}
                            </option>
                        ))}
                    </select>
                </div>

                {data.warnings.length > 0 && (
                    <div className="commander-warning">
                        {data.warnings.map((warning) => <div key={warning}>{warning}</div>)}
                    </div>
                )}

                <div className="commander-summary-grid">
                    <div>
                        <span>Current race</span>
                        <strong>{raceName(dossier.race_id)}</strong>
                        <small>canonical current-game slot</small>
                    </div>
                    <div>
                        <span>Public history</span>
                        <strong>{dossier.public_history_game_count ?? "UNKNOWN"}</strong>
                        <small>running + finished games</small>
                    </div>
                    <div>
                        <span>Known peers with shared history</span>
                        <strong>
                            {dossier.current_game_peer_history.filter((peer) => peer.shared_games > 0).length}
                        </strong>
                        <small>other shared games; no relationship label</small>
                    </div>
                    <div>
                        <span>History source</span>
                        <strong>{dossier.history_provenance.cache_state}</strong>
                        <small>{dossier.history_provenance.source}</small>
                    </div>
                </div>
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <h2>Shared history with current-game peers</h2>
                        <p>Previous shared games exclude the selected sector. Expand a pair for source-game participation and links.</p>
                    </div>
                </div>
                <div className="commander-peer-list">
                    {pairs.map((pair) => {
                        const peer = pair.player_a === dossier.username
                            ? pair.player_b
                            : pair.player_a;
                        return (
                            <details className="commander-peer" key={pair.player_a + "::" + pair.player_b}>
                                <summary>
                                    <span>
                                        <strong>{peer}</strong>
                                        <small>
                                            {pair.shared_games === null
                                                ? "history unavailable"
                                                : pair.shared_games + " other shared games"}
                                        </small>
                                    </span>
                                    <span>
                                        <strong>
                                            {pair.shared_games === null
                                                ? "UNKNOWN"
                                                : exactOrLowerBound(
                                                    pair.overlapping_turn_count,
                                                    pair.known_overlapping_turn_count,
                                                )}
                                        </strong>
                                        <small>
                                            {pair.overlap_reconstruction_complete
                                                ? "overlapping turns"
                                                : "known overlapping turns"}
                                        </small>
                                    </span>
                                </summary>
                                <PairDetails pair={pair} />
                            </details>
                        );
                    })}
                </div>
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <h2>Attributable race history</h2>
                        <p>{dossier.race_history_coverage.basis}</p>
                    </div>
                </div>
                <div className="commander-race-list">
                    {raceSummary.length === 0 ? (
                        <p className="muted">No attributable race records.</p>
                    ) : raceSummary.map((item) => (
                        <div key={item.label}>
                            <strong>{item.label}</strong>
                            <span>{item.games} reconstructed game{item.games === 1 ? "" : "s"}</span>
                        </div>
                    ))}
                </div>
                <p className="commander-provenance">
                    Coverage: {dossier.race_history_coverage.games_with_attributable_race}
                    {" attributable games / "}
                    {dossier.race_history_coverage.public_history_games ?? "unknown"}
                    {" public-history games. This is intentionally not presented as complete."}
                </p>
            </section>

            <section className="panel">
                <details>
                    <summary className="commander-history-summary">
                        Public running/finished game history · {dossier.public_history_game_count ?? "UNKNOWN"}
                    </summary>
                    <div className="commander-history-list">
                        {dossier.public_history_games.map((game) => (
                            <div key={game.game_id}>
                                <span>
                                    <strong>{game.name}</strong>
                                    <small>#{game.game_id}</small>
                                </span>
                                <span>
                                    {game.status_name || "status " + game.status_id}
                                    {game.turn === null ? "" : " · T" + game.turn}
                                </span>
                            </div>
                        ))}
                    </div>
                    <p className="commander-provenance">
                        {dossier.history_provenance.source} · {dossier.history_provenance.cache_state}
                        {dossier.history_provenance.fetched_at === null
                            ? ""
                            : " · fetched " + dossier.history_provenance.fetched_at}
                    </p>
                </details>
            </section>

            <section className="panel commander-boundary">
                <strong>Evidence boundary</strong>
                <p>
                    Public factual observations are cached separately from this
                    derived summary. Participation overlap is reconstructed from
                    public loadinfo event/roster evidence. Unknown interval bounds
                    remain UNKNOWN. No behavioral inference is produced and no
                    factual game state is mutated.
                </p>
            </section>
        </div>
    );
}
