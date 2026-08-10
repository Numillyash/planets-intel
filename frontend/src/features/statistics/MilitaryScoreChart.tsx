import type {
    PlayerInfo,
    ScoreHistoryItem,
} from "../../types/api";


interface MilitaryScoreChartProps {
    players: PlayerInfo[];
    history: ScoreHistoryItem[];
}


const WIDTH = 1000;
const HEIGHT = 420;

const PADDING_LEFT = 78;
const PADDING_RIGHT = 28;
const PADDING_TOP = 26;
const PADDING_BOTTOM = 54;

const plotWidth =
    WIDTH - PADDING_LEFT - PADDING_RIGHT;

const plotHeight =
    HEIGHT - PADDING_TOP - PADDING_BOTTOM;


function playerColor(
    slotId: number,
): string {
    const hue = (slotId * 47) % 360;

    return `hsl(${hue} 72% 60%)`;
}


function formatScore(
    value: number,
): string {
    if (value >= 1_000_000) {
        return `${(value / 1_000_000).toFixed(1)}M`;
    }

    if (value >= 1_000) {
        return `${Math.round(value / 1_000)}k`;
    }

    return String(value);
}


export function MilitaryScoreChart({
    players,
    history,
}: MilitaryScoreChartProps) {
    if (history.length === 0) {
        return null;
    }

    const turns = history.map(
        (item) => item.turn,
    );

    const minTurn = Math.min(...turns);
    const maxTurn = Math.max(...turns);

    const maxScore = Math.max(
        ...history.map(
            (item) => item.military_score,
        ),
        1,
    );

    const turnRange = Math.max(
        maxTurn - minTurn,
        1,
    );

    const xForTurn = (
        turn: number,
    ): number =>
        PADDING_LEFT +
        ((turn - minTurn) / turnRange) *
            plotWidth;

    const yForScore = (
        score: number,
    ): number =>
        PADDING_TOP +
        plotHeight -
        (score / maxScore) * plotHeight;

    const historyBySlot =
        new Map<number, ScoreHistoryItem[]>();

    for (const item of history) {
        const list =
            historyBySlot.get(item.slot_id) ??
            [];

        list.push(item);

        historyBySlot.set(
            item.slot_id,
            list,
        );
    }

    for (const list of historyBySlot.values()) {
        list.sort(
            (a, b) => a.turn - b.turn,
        );
    }

    const yTicks = 5;

    return (
        <section className="panel chart-panel">
            <div className="panel-header">
                <div>
                    <h2>Military score history</h2>
                    <p>
                        Public score data · turns{" "}
                        {minTurn}–{maxTurn}
                    </p>
                </div>
            </div>

            <div className="chart-wrapper">
                <svg
                    className="score-chart"
                    viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                    role="img"
                    aria-label="Military score history"
                >
                    {Array.from(
                        {
                            length: yTicks + 1,
                        },
                        (_, index) => {
                            const ratio =
                                index / yTicks;

                            const y =
                                PADDING_TOP +
                                plotHeight -
                                ratio *
                                    plotHeight;

                            const score =
                                maxScore *
                                ratio;

                            return (
                                <g key={index}>
                                    <line
                                        className="chart-grid"
                                        x1={
                                            PADDING_LEFT
                                        }
                                        y1={y}
                                        x2={
                                            WIDTH -
                                            PADDING_RIGHT
                                        }
                                        y2={y}
                                    />

                                    <text
                                        className="chart-axis-label"
                                        x={
                                            PADDING_LEFT -
                                            12
                                        }
                                        y={y + 4}
                                        textAnchor="end"
                                    >
                                        {formatScore(
                                            score,
                                        )}
                                    </text>
                                </g>
                            );
                        },
                    )}

                    <line
                        className="chart-axis"
                        x1={PADDING_LEFT}
                        y1={
                            PADDING_TOP +
                            plotHeight
                        }
                        x2={
                            WIDTH -
                            PADDING_RIGHT
                        }
                        y2={
                            PADDING_TOP +
                            plotHeight
                        }
                    />

                    <text
                        className="chart-axis-label"
                        x={PADDING_LEFT}
                        y={
                            HEIGHT -
                            PADDING_BOTTOM +
                            28
                        }
                        textAnchor="middle"
                    >
                        {minTurn}
                    </text>

                    <text
                        className="chart-axis-label"
                        x={
                            WIDTH -
                            PADDING_RIGHT
                        }
                        y={
                            HEIGHT -
                            PADDING_BOTTOM +
                            28
                        }
                        textAnchor="middle"
                    >
                        {maxTurn}
                    </text>

                    {players.map(
                        (player) => {
                            const points =
                                historyBySlot.get(
                                    player.slot_id,
                                );

                            if (
                                !points ||
                                points.length === 0
                            ) {
                                return null;
                            }

                            const polyline =
                                points
                                    .map(
                                        (item) =>
                                            `${xForTurn(
                                                item.turn,
                                            )},${yForScore(
                                                item.military_score,
                                            )}`,
                                    )
                                    .join(" ");

                            return (
                                <polyline
                                    key={
                                        player.slot_id
                                    }
                                    className="score-line"
                                    points={polyline}
                                    fill="none"
                                    stroke={playerColor(
                                        player.slot_id,
                                    )}
                                />
                            );
                        },
                    )}
                </svg>
            </div>

            <div className="chart-legend">
                {players.map((player) => (
                    <div
                        key={player.slot_id}
                        className="legend-item"
                    >
                        <span
                            className="legend-color"
                            style={{
                                backgroundColor:
                                    playerColor(
                                        player.slot_id,
                                    ),
                            }}
                        />

                        <span>
                            {player.slot_id}.{" "}
                            {player.username}
                        </span>
                    </div>
                ))}
            </div>
        </section>
    );
}
