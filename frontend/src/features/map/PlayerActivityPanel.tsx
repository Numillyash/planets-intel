import { useEffect, useMemo, useState } from "react";
import { getPlayerActivity } from "../../api/activity";
import type { PlayerActivityItem } from "../../types/activity";
import "./player-activity.css";

const DAY_MINUTES = 24 * 60;
const DENSITY_POINTS = 97;
const DENSITY_SIGMA_MINUTES = 70;
const CHART_WIDTH = 300;
const CHART_HEIGHT = 86;
const CHART_BASELINE = 70;
const CHART_AMPLITUDE = 54;

type TimingScope = "all-current" | "this-game";
type TimingZone = "local" | "utc";

function localOffsetMinutes(): number {
    return -new Date().getTimezoneOffset();
}

function browserTimezoneName(): string {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "browser local";
}

function localMinute(utcMinute: number): number {
    const offsetMinutes = localOffsetMinutes();
    return ((Math.trunc(utcMinute) + offsetMinutes) % DAY_MINUTES + DAY_MINUTES) % DAY_MINUTES;
}

function sampleMinute(utcMinute: number, zone: TimingZone): number {
    return zone === "local"
        ? localMinute(utcMinute)
        : ((Math.trunc(utcMinute) % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
}

function formatUtcOffset(): string {
    const total = localOffsetMinutes();
    const sign = total >= 0 ? "+" : "-";
    const absolute = Math.abs(total);
    return `UTC${sign}${String(Math.floor(absolute / 60)).padStart(2, "0")}:${String(absolute % 60).padStart(2, "0")}`;
}

function formatAxisMinute(minute: number): string {
    const wrapped = ((Math.round(minute) % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
    const hour = Math.floor(wrapped / 60);
    const rest = wrapped % 60;
    return rest === 0
        ? String(hour).padStart(2, "0")
        : `${String(hour).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatDelay(minutes: number | null): string {
    if (minutes === null || !Number.isFinite(minutes) || minutes < 0) return "—";
    const rounded = Math.round(minutes);
    const hours = Math.floor(rounded / 60);
    const rest = rounded % 60;
    if (hours === 0) return `${rest}m`;
    if (rest === 0) return `${hours}h`;
    return `${hours}h ${rest}m`;
}

function circularDistance(left: number, right: number): number {
    const direct = Math.abs(left - right);
    return Math.min(direct, DAY_MINUTES - direct);
}

function smoothedDensity(values: number[], zone: TimingZone): number[] {
    const clockSamples = values
        .filter(Number.isFinite)
        .map((minute) => sampleMinute(minute, zone));
    if (clockSamples.length === 0) {
        return Array.from({ length: DENSITY_POINTS }, () => 0);
    }

    const density = Array.from({ length: DENSITY_POINTS }, (_, index) => {
        const minute = index === DENSITY_POINTS - 1
            ? 0
            : index * DAY_MINUTES / (DENSITY_POINTS - 1);
        return clockSamples.reduce((sum, sample) => {
            const distance = circularDistance(minute, sample);
            const z = distance / DENSITY_SIGMA_MINUTES;
            return sum + Math.exp(-0.5 * z * z);
        }, 0);
    });
    const maximum = Math.max(...density, 1e-9);
    return density.map((value) => value / maximum);
}

function densityLinePath(density: number[]): string {
    return density.map((value, index) => {
        const x = index * CHART_WIDTH / Math.max(1, density.length - 1);
        const y = CHART_BASELINE - value * CHART_AMPLITUDE;
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(" ");
}

function densityAreaPath(density: number[]): string {
    const line = densityLinePath(density);
    return `${line} L${CHART_WIDTH},${CHART_BASELINE} L0,${CHART_BASELINE} Z`;
}

function currentLocalMinute(now: Date): number {
    return now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60;
}

function currentUtcMinute(now: Date): number {
    return now.getUTCHours() * 60 + now.getUTCMinutes() + now.getUTCSeconds() / 60;
}

function SmoothTimingChart({
    label,
    values,
    kind,
    gameCount,
    now,
    zone,
}: {
    label: string;
    values: number[];
    kind: "open" | "ready";
    gameCount: number;
    now: Date;
    zone: TimingZone;
}) {
    const density = useMemo(() => smoothedDensity(values, zone), [values, zone]);
    const linePath = useMemo(() => densityLinePath(density), [density]);
    const areaPath = useMemo(() => densityAreaPath(density), [density]);
    // One clock is shared by every card and chart; see PlayerActivityPanel.
    // Each axis begins at midnight; the marker, density and factual ticks use the same zone.
    const nowMinute = zone === "local" ? currentLocalMinute(now) : currentUtcMinute(now);
    const nowX = nowMinute * CHART_WIDTH / DAY_MINUTES;
    const nowLabel = `Current time · ${formatAxisMinute(currentLocalMinute(now))} local / ${formatAxisMinute(currentUtcMinute(now))} UTC`;
    const axisTicks = [0, 360, 720, 1080, 1440];

    return (
        <div className={`turn-timing-density is-${kind}`}>
            <div className="turn-timing-density-heading">
                <strong>{label}</strong>
                <span>
                    {values.length} turn{values.length === 1 ? "" : "s"}
                    {gameCount > 1 ? ` · ${gameCount} games` : ""}
                </span>
            </div>

            <div className="turn-timing-axis-name">{zone === "local" ? "LOCAL" : "UTC"} · 00:00–24:00</div>

            <svg
                aria-label={`${label} smoothed ${zone === "local" ? "local" : "UTC"} time-of-day distribution from ${values.length} factual turn observations. ${nowLabel} is the solid yellow current-time marker, not an average.`}
                className="turn-timing-density-svg"
                preserveAspectRatio="none"
                role="img"
                viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            >
                <title>{nowLabel} — solid yellow line marks the current time, not the mean.</title>
                <line className="turn-timing-grid-line" x1="0" x2={CHART_WIDTH} y1="43" y2="43" />
                <line className="turn-timing-grid-line" x1="0" x2={CHART_WIDTH} y1={CHART_BASELINE} y2={CHART_BASELINE} />
                {values.length > 0 && (
                    <>
                        <path className="turn-timing-density-area" d={areaPath} />
                        <path className="turn-timing-density-line" d={linePath} />
                    </>
                )}
                {values.filter(Number.isFinite).map((raw, index) => {
                    const x = sampleMinute(raw, zone) * CHART_WIDTH / DAY_MINUTES;
                    return (
                        <line
                            className="turn-timing-sample-tick"
                            key={`${raw}-${index}`}
                            x1={x}
                            x2={x}
                            y1={CHART_BASELINE + 2}
                            y2={CHART_BASELINE + 8}
                        />
                    );
                })}
                <line
                    className="turn-timing-now-line"
                    data-now-minute={nowMinute.toFixed(2)}
                    x1={nowX}
                    x2={nowX}
                    y1="4"
                    y2={CHART_BASELINE + 8}
                />
            </svg>

            <div className="turn-timing-day-axis" data-axis-zone={zone} aria-label={`${zone === "local" ? "Local" : "UTC"} time-of-day axis from midnight to midnight`}>
                {axisTicks.map((minute) => (
                    <span key={minute} data-axis-minute={minute} style={{ left: `${minute * 100 / DAY_MINUTES}%` }}>
                        {minute === DAY_MINUTES ? "24" : formatAxisMinute(minute)}
                    </span>
                ))}
            </div>
        </div>
    );
}

function ActivityCard({
    item,
    scope,
    now,
    zone,
}: {
    item: PlayerActivityItem;
    scope: TimingScope;
    now: Date;
    zone: TimingZone;
}) {
    const aggregate = scope === "all-current";
    const openValues = aggregate
        ? item.all_current_games_open_utc_minutes ?? []
        : item.open_utc_minutes ?? [];
    const readyValues = aggregate
        ? item.all_current_games_ready_utc_minutes ?? []
        : item.ready_utc_minutes ?? [];
    const gameCount = aggregate ? item.all_current_games_count : 1;
    const confidence = aggregate
        ? item.all_current_games_prediction_confidence
        : item.prediction_confidence;

    return (
        <article className="turn-timing-player-card">
            <header>
                <div>
                    <strong>{item.username}</strong>
                    <small>
                        slot {item.slot_id} · {confidence} sample confidence
                        {aggregate ? ` · combined from ${gameCount} current game${gameCount === 1 ? "" : "s"}` : " · selected game only"}
                    </small>
                </div>
                <span className={`turn-timing-state is-${item.current_state}`}>
                    {item.current_state.split("_").join(" ")}
                </span>
            </header>

            <div className="turn-timing-chart-grid">
                <SmoothTimingChart
                    gameCount={gameCount}
                    kind="ready"
                    now={now}
                    zone={zone}
                    label="Turn ready"
                    values={readyValues}
                />
                <SmoothTimingChart
                    gameCount={gameCount}
                    kind="open"
                    now={now}
                    zone={zone}
                    label="First observed open"
                    values={openValues}
                />
            </div>

            <div className="turn-timing-latency-row">
                <span>
                    Median first observed open after host (this game)
                    <strong>{formatDelay(item.median_open_after_host_minutes)}</strong>
                </span>
            </div>
        </article>
    );
}

export function PlayerActivityPanel(props: {
    gameId: number;
    throughTurn: number;
    embedded?: boolean;
}) {
    const [items, setItems] = useState<PlayerActivityItem[]>([]);
    const [currentGamesConsidered, setCurrentGamesConsidered] = useState(0);
    const [scope, setScope] = useState<TimingScope>("all-current");
    const [zone, setZone] = useState<TimingZone>("local");
    const [open, setOpen] = useState(props.embedded ?? false);
    const [now, setNow] = useState(() => new Date());

    // A single live clock drives every chart; 30 seconds is ample for
    // time-of-day context without mounting a timer for every player.
    useEffect(() => {
        const timer = window.setInterval(() => setNow(new Date()), 30 * 1000);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        if (props.embedded) setOpen(true);
    }, [props.embedded]);

    useEffect(() => {
        let active = true;
        async function load() {
            try {
                const data = await getPlayerActivity(props.gameId, props.throughTurn);
                if (active) {
                    setItems(data.players);
                    setCurrentGamesConsidered(data.current_games_considered ?? 0);
                }
            } catch {
                if (active) {
                    setItems([]);
                    setCurrentGamesConsidered(0);
                }
            }
        }
        void load();
        const timer = window.setInterval(() => void load(), 5 * 60 * 1000);
        return () => { active = false; window.clearInterval(timer); };
    }, [props.gameId, props.throughTurn]);

    if (!open && !props.embedded) {
        return (
            <button
                className="secondary-button"
                onClick={() => setOpen(true)}
                type="button"
            >
                Turn timing · {items.length}
            </button>
        );
    }

    const visibleItems = items.filter(
        (item) => item.current_state !== "dead" && item.race_id < 100,
    );

    return (
        <section className={props.embedded ? "panel dashboard-embedded-panel turn-timing-panel" : undefined}>
            <div className="turn-timing-panel-inner">
                <div className="turn-timing-panel-heading">
                    <div>
                        <div className="eyebrow">TURN TIMING · THROUGH T{props.throughTurn}</div>
                        <h2>Player activity across the day</h2>
                        <p>
                            Smooth curves preserve separate morning/evening habits instead of collapsing
                            them into one average. Raw ticks under each curve are the factual per-turn samples.
                        </p>
                        <div className="turn-timing-time-reference">
                            <span><strong>LOCAL</strong> {browserTimezoneName()} · {formatUtcOffset()}</span>
                            <span><strong>GLOBAL</strong> UTC</span>
                            <span className="turn-timing-now-reference" data-testid="turn-timing-now-clock">
                                <i aria-hidden="true" />
                                <strong>NOW</strong>
                                {formatAxisMinute(currentLocalMinute(now))} local
                                {" / "}{formatAxisMinute(currentUtcMinute(now))} UTC
                            </span>
                        </div>
                    </div>
                    <div className="turn-timing-heading-actions">
                        <div className="turn-timing-scope" role="group" aria-label="Chart timezone">
                            <button type="button" data-testid="turn-timing-zone-local" aria-pressed={zone === "local"}
                                className={zone === "local" ? "is-active" : ""} onClick={() => setZone("local")}>LOCAL</button>
                            <button type="button" data-testid="turn-timing-zone-utc" aria-pressed={zone === "utc"}
                                className={zone === "utc" ? "is-active" : ""} onClick={() => setZone("utc")}>UTC</button>
                        </div>
                        <div className="turn-timing-scope" aria-label="Timing data scope">
                            <button
                                className={scope === "all-current" ? "is-active" : ""}
                                onClick={() => setScope("all-current")}
                                type="button"
                            >
                                All current games
                            </button>
                            <button
                                className={scope === "this-game" ? "is-active" : ""}
                                onClick={() => setScope("this-game")}
                                type="button"
                            >
                                This game
                            </button>
                        </div>
                        {!props.embedded && (
                            <button
                                className="secondary-button"
                                onClick={() => setOpen(false)}
                                type="button"
                            >
                                Hide
                            </button>
                        )}
                    </div>
                </div>

                {scope === "all-current" && (
                    <div className="turn-timing-scope-note">
                        Combining same canonical usernames across {currentGamesConsidered} Running/Joining game{currentGamesConsidered === 1 ? "" : "s"}{" "}
                        accessible to your active linked observers. Ambiguous same-game identities are excluded.
                    </div>
                )}

                {visibleItems.length === 0 ? (
                    <p className="subtitle">No activity samples are available yet.</p>
                ) : (
                    <div className="turn-timing-player-grid">
                        {visibleItems.map((item) => (
                            <ActivityCard item={item} key={item.slot_id} now={now} scope={scope} zone={zone} />
                        ))}
                    </div>
                )}

                <p className="turn-timing-note">
                    Each chart shows one time-of-day axis starting at midnight. Switch LOCAL/UTC to rotate factual ticks,
                    smoothed curves and the current-time marker together; the two clocks remain visible above.
                    Curves are circular presentation smoothing of factual time-of-day samples and are normalized per
                    chart, so curve height represents habit shape rather than an absolute probability.
                    The solid yellow line (identified in the NOW legend above) marks current time on the selected axis and updates automatically;
                    it is not an average of player activity.
                    First-open and its after-host delay are bounded by the polling interval; Ready uses Planets.nu turnreadydate
                    when available. A ready-after-host median is not displayed because ready timestamps can predate the
                    matching host timestamp and an apparent 0m may be misleading. These observations describe game-turn activity, not continuous online presence.
                </p>
            </div>
        </section>
    );
}
