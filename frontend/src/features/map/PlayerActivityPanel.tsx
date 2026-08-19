import { useEffect, useState } from "react";
import { getPlayerActivity } from "../../api/activity";
import type { PlayerActivityItem } from "../../types/activity";
import "./player-activity.css";

function localMinute(utcMinute: number): number {
    const offsetMinutes = -new Date().getTimezoneOffset();
    return ((Math.trunc(utcMinute) + offsetMinutes) % 1440 + 1440) % 1440;
}

function localHourCounts(utcMinutes: number[]): number[] {
    const counts = Array.from({ length: 24 }, () => 0);
    for (const raw of utcMinutes) {
        if (!Number.isFinite(raw)) continue;
        counts[Math.floor(localMinute(raw) / 60)] += 1;
    }
    return counts;
}

function formatLocalMinute(utcMinute: number | null): string {
    if (utcMinute === null || !Number.isFinite(utcMinute)) return "—";
    const minute = localMinute(utcMinute);
    const hour = Math.floor(minute / 60);
    const rest = minute % 60;
    return `${String(hour).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatDelay(minutes: number | null): string {
    if (minutes === null || !Number.isFinite(minutes)) return "—";
    const rounded = Math.max(0, Math.round(minutes));
    const hours = Math.floor(rounded / 60);
    const rest = rounded % 60;
    if (hours === 0) return `${rest}m`;
    if (rest === 0) return `${hours}h`;
    return `${hours}h ${rest}m`;
}

function TimingHistogram({
    label,
    values,
    kind,
}: {
    label: string;
    values: number[];
    kind: "open" | "ready";
}) {
    const counts = localHourCounts(values);
    const maximum = Math.max(1, ...counts);

    return (
        <div className={`turn-timing-histogram is-${kind}`}>
            <div className="turn-timing-histogram-heading">
                <strong>{label}</strong>
                <span>{values.length} turn{values.length === 1 ? "" : "s"}</span>
            </div>
            <div
                aria-label={`${label} local-time distribution`}
                className="turn-timing-bars"
                role="img"
            >
                {counts.map((count, hour) => (
                    <span
                        className="turn-timing-bar-cell"
                        key={hour}
                        title={`${String(hour).padStart(2, "0")}:00–${String(hour).padStart(2, "0")}:59 · ${count}`}
                    >
                        <span
                            className="turn-timing-bar"
                            style={{
                                height: count === 0
                                    ? 0
                                    : `${Math.max(12, count * 100 / maximum)}%`,
                            }}
                        />
                    </span>
                ))}
            </div>
            <div className="turn-timing-axis" aria-hidden="true">
                <span>00</span><span>06</span><span>12</span><span>18</span><span>24</span>
            </div>
        </div>
    );
}

function ActivityCard({ item }: { item: PlayerActivityItem }) {
    return (
        <article className="turn-timing-player-card">
            <header>
                <div>
                    <strong>{item.username}</strong>
                    <small>slot {item.slot_id} · {item.prediction_confidence} confidence</small>
                </div>
                <span className={`turn-timing-state is-${item.current_state}`}>
                    {item.current_state.split("_").join(" ")}
                </span>
            </header>

            <div className="turn-timing-chart-grid">
                <TimingHistogram
                    kind="open"
                    label="First observed open"
                    values={item.open_utc_minutes ?? []}
                />
                <TimingHistogram
                    kind="ready"
                    label="Turn ready"
                    values={item.ready_utc_minutes ?? []}
                />
            </div>

            <div className="turn-timing-summary-row">
                <span title="Secondary circular-center summary. Use the histogram above for bimodal or multimodal habits.">
                    Typical open
                    <strong>{formatLocalMinute(item.typical_open_utc_minute)}</strong>
                </span>
                <span title="Secondary circular-center summary. Use the histogram above for bimodal or multimodal habits.">
                    Typical ready
                    <strong>{formatLocalMinute(item.typical_ready_utc_minute)}</strong>
                </span>
            </div>

            <div className="turn-timing-latency-row">
                <span>
                    Median open after host
                    <strong>{formatDelay(item.median_open_after_host_minutes)}</strong>
                </span>
                <span>
                    Median ready after host
                    <strong>{formatDelay(item.median_ready_after_host_minutes)}</strong>
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
    const [open, setOpen] = useState(props.embedded ?? false);

    useEffect(() => {
        if (props.embedded) setOpen(true);
    }, [props.embedded]);

    useEffect(() => {
        let active = true;
        async function load() {
            try {
                const data = await getPlayerActivity(props.gameId, props.throughTurn);
                if (active) setItems(data.players);
            } catch {
                if (active) setItems([]);
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

    const visibleItems = items.filter((item) => item.current_state !== "dead");

    return (
        <section className={props.embedded ? "panel dashboard-embedded-panel turn-timing-panel" : undefined}>
            <div className="turn-timing-panel-inner">
                <div className="turn-timing-panel-heading">
                    <div>
                        <div className="eyebrow">TURN TIMING · THROUGH T{props.throughTurn}</div>
                        <h2>Player activity by local hour</h2>
                        <p>
                            Each bar is a per-turn observation. Multiple daily habits stay
                            visible as separate peaks instead of being collapsed into one average.
                        </p>
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

                {visibleItems.length === 0 ? (
                    <p className="subtitle">No activity samples are available yet.</p>
                ) : (
                    <div className="turn-timing-player-grid">
                        {visibleItems.map((item) => (
                            <ActivityCard item={item} key={item.slot_id} />
                        ))}
                    </div>
                )}

                <p className="turn-timing-note">
                    Times are shown in this browser&apos;s local timezone. First-open time is
                    bounded by the polling interval; Ready uses Planets.nu turnreadydate when available.
                    Typical times are secondary circular-center summaries; the histograms are the source
                    for multimodal habits. These observations describe game-turn activity, not continuous
                    online presence.
                </p>
            </div>
        </section>
    );
}
