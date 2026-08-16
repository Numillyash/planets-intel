import type {
    PlayerInfo,
    ScoreHistoryItem,
} from "../../types/api";
import { raceName } from "../../lib/races";


interface PlayersTableProps {
    players: PlayerInfo[];
    latestScores: Map<number, ScoreHistoryItem>;
    snapshotTurn?: number | null;
}


function formatDelta(
    value: number | null | undefined,
): string {
    if (value === null || value === undefined) {
        return "—";
    }

    if (value > 0) {
        return `+${value}`;
    }

    return String(value);
}


export function PlayersTable({
    players,
    latestScores,
    snapshotTurn = null,
}: PlayersTableProps) {
    const historical = snapshotTurn !== null;

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Players</h2>
                    <p>
                        {historical
                            ? `Public score snapshot · turn ${snapshotTurn}`
                            : "Current public score snapshot"}
                    </p>
                </div>
            </div>

            <div className="table-wrapper">
                <table className="players-table">
                    <thead>
                        <tr>
                            <th>Slot</th>
                            <th>Player</th>
                            <th>Race</th>
                            <th>Planets</th>
                            <th>Ships</th>
                            <th>Bases</th>
                            <th>Military</th>
                            <th>Δ Military</th>
                            <th>Ready</th>
                        </tr>
                    </thead>

                    <tbody>
                        {players.map((player) => {
                            const score = latestScores.get(
                                player.slot_id,
                            );
                            const scoreShips = score === undefined
                                ? null
                                : score.capital_ships + score.freighters;

                            const isDead = !historical && (
                                player.status !== 1 ||
                                player.username === "dead"
                            );

                            return (
                                <tr
                                    key={player.slot_id}
                                    className={
                                        isDead
                                            ? "player-dead"
                                            : undefined
                                    }
                                >
                                    <td>
                                        {player.slot_id}
                                    </td>

                                    <td className="player-name">
                                        {player.username}
                                    </td>

                                    <td>
                                        {raceName(player.race_id)}
                                    </td>

                                    <td>
                                        {score?.planets ??
                                            (historical ? "—" : player.planets)}
                                    </td>

                                    <td>
                                        {scoreShips ??
                                            (historical ? "—" : player.ships)}
                                    </td>

                                    <td>
                                        {score?.starbases ??
                                            (historical ? "—" : player.starbases)}
                                    </td>

                                    <td className="numeric-important">
                                        {score?.military_score.toLocaleString() ??
                                            "—"}
                                    </td>

                                    <td
                                        className={
                                            score &&
                                            score.delta_military_score !==
                                                null
                                                ? score.delta_military_score >
                                                  0
                                                    ? "delta-positive"
                                                    : score.delta_military_score <
                                                        0
                                                      ? "delta-negative"
                                                      : ""
                                                : ""
                                        }
                                    >
                                        {formatDelta(
                                            score?.delta_military_score,
                                        )}
                                    </td>

                                    <td>
                                        {historical
                                            ? "—"
                                            : player.turn_ready
                                                ? "Ready"
                                                : "—"}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
