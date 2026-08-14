import { useEffect, useMemo, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import {
    getVcrReplayTrace,
    type VcrReplayFrame,
    type VcrReplaySideFrame,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";
import {
    privateHullAssetUrl,
    privatePlanetAssetUrl,
} from "../../lib/privateAssets";
import type {
    CombatEventSideSummary,
    CombatEventSummary,
} from "../../types/history";
import "./vcr-hull-artwork.css";

function sideName(side: CombatEventSideSummary): string {
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}

function eventTitle(event: CombatEventSummary): string {
    return `${sideName(event.sides[0])} vs ${sideName(event.sides[1])}`;
}

function sideMarkerClass(side: VcrReplaySideFrame): string {
    return side.is_planet ? "is-planet" : "is-ship";
}

function CombatObjectArtwork({
    side,
    facing,
}: {
    side: VcrReplaySideFrame;
    facing: "left" | "right";
}) {
    const assetUrl = side.is_planet
        ? privatePlanetAssetUrl()
        : privateHullAssetUrl(side.image_id ?? side.hull_id);
    const [ready, setReady] = useState(false);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setReady(false);
        setLoaded(false);

        if (assetUrl === null) {
            return () => {
                cancelled = true;
            };
        }

        void (async () => {
            for (let attempt = 1; attempt <= 3; attempt += 1) {
                try {
                    const response = await fetch(assetUrl, {
                        credentials: "same-origin",
                        cache: "force-cache",
                        headers: { Accept: "image/png" },
                    });
                    if (!response.ok) {
                        throw new Error(`Artwork HTTP ${response.status}`);
                    }
                    await response.blob();
                    if (!cancelled) setReady(true);
                    return;
                } catch {
                    if (attempt < 3) {
                        await new Promise((resolve) => {
                            window.setTimeout(resolve, attempt * 650);
                        });
                    }
                }
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [assetUrl]);

    if (assetUrl === null) {
        return <span className="vcr-object-marker" />;
    }

    return (
        <span
            className={
                `vcr-hull-artwork-shell is-facing-${facing}`
                + (side.is_planet ? " is-planet-artwork" : "")
            }
        >
            {ready && (
                <img
                    alt=""
                    className="vcr-hull-artwork"
                    draggable={false}
                    hidden={!loaded}
                    onError={() => setLoaded(false)}
                    onLoad={() => setLoaded(true)}
                    src={assetUrl}
                />
            )}
            <span
                className="vcr-object-marker"
                hidden={ready && loaded}
            />
        </span>
    );
}

function SideStatus({
    label,
    side,
}: {
    label: string;
    side: VcrReplaySideFrame;
}) {
    return (
        <article className="vcr-status-card">
            <div>
                <span>{label}</span>
                <strong>{side.name ?? `Object #${side.object_id ?? "?"}`}</strong>
            </div>
            <dl>
                <div><dt>Shield</dt><dd>{side.shield}%</dd></div>
                <div><dt>Damage</dt><dd>{side.damage}%</dd></div>
                <div><dt>Crew</dt><dd>{side.crew}</dd></div>
                <div><dt>Torps</dt><dd>{side.torpedoes}</dd></div>
                <div><dt>Fighters</dt><dd>{side.fighters}</dd></div>
                <div><dt>Out</dt><dd>{side.fighters_out}</dd></div>
            </dl>
            <div className="vcr-charge-bars">
                {side.beam_charge !== null && (
                    <label>
                        <span>Beams</span>
                        <progress max={100} value={Math.min(100, side.beam_charge)} />
                    </label>
                )}
                {side.launcher_charge !== null && (
                    <label>
                        <span>Launchers</span>
                        <progress max={100} value={Math.min(100, side.launcher_charge)} />
                    </label>
                )}
            </div>
        </article>
    );
}

const TORPEDO_PRESENTATION_FRAMES = 10;

function combatPercent(x: number): number {
    return Math.max(4, Math.min(96, (x / 640) * 100));
}

interface TorpedoPresentation {
    key: string;
    side: "left" | "right";
    x: number;
    hit: boolean;
}

function activeTorpedoPresentations(
    frames: VcrReplayFrame[],
    frameIndex: number,
): TorpedoPresentation[] {
    const result: TorpedoPresentation[] = [];

    for (const side of ["left", "right"] as const) {
        const eventName = `${side}_torpedo`;
        const hitName = side === "left" ? "right_hit" : "left_hit";

        for (
            let launchIndex = frameIndex;
            launchIndex >= Math.max(0, frameIndex - TORPEDO_PRESENTATION_FRAMES + 1);
            launchIndex -= 1
        ) {
            const launchFrame = frames[launchIndex];
            if (!launchFrame.events.includes(eventName)) continue;

            const age = frameIndex - launchIndex;
            const progress = Math.min(
                1,
                (age + 1) / TORPEDO_PRESENTATION_FRAMES,
            );
            const launchSide = side === "left"
                ? launchFrame.left
                : launchFrame.right;
            const targetSide = side === "left"
                ? launchFrame.right
                : launchFrame.left;
            const x = launchSide.x + (targetSide.x - launchSide.x) * progress;

            result.push({
                key: `${side}-${launchIndex}`,
                side,
                x: combatPercent(x),
                hit: launchFrame.events.includes(hitName),
            });
            break;
        }
    }

    return result;
}

function Battlefield({
    frame,
    frames,
    frameIndex,
}: {
    frame: VcrReplayFrame;
    frames: VcrReplayFrame[];
    frameIndex: number;
}) {
    const leftPercent = combatPercent(frame.left.x);
    const rightPercent = combatPercent(frame.right.x);
    const hitLeft = frame.events.includes("left_hit");
    const hitRight = frame.events.includes("right_hit");
    const torpedoes = activeTorpedoPresentations(frames, frameIndex);

    return (
        <div className="vcr-battlefield">
            <div className="vcr-range-line" />

            {torpedoes.map((torpedo) => (
                <span
                    aria-hidden="true"
                    className={
                        `vcr-torpedo-projectile is-${torpedo.side}`
                        + (torpedo.hit ? " is-hit-course" : "")
                    }
                    key={torpedo.key}
                    style={{ left: `${torpedo.x}%` }}
                >
                    <span />
                </span>
            ))}

            <div
                className={
                    `vcr-combat-object ${sideMarkerClass(frame.left)}`
                    + (hitLeft ? " is-hit" : "")
                }
                style={{ left: `${leftPercent}%` }}
            >
                <CombatObjectArtwork facing="right" side={frame.left} />
                <strong>{frame.left.name ?? `#${frame.left.object_id ?? "?"}`}</strong>
                {frame.left.fighters_out > 0 && (
                    <small>{frame.left.fighters_out} fighters out</small>
                )}
            </div>

            <div
                className={
                    `vcr-combat-object ${sideMarkerClass(frame.right)}`
                    + (hitRight ? " is-hit" : "")
                }
                style={{ left: `${rightPercent}%` }}
            >
                <CombatObjectArtwork facing="left" side={frame.right} />
                <strong>{frame.right.name ?? `#${frame.right.object_id ?? "?"}`}</strong>
                {frame.right.fighters_out > 0 && (
                    <small>{frame.right.fighters_out} fighters out</small>
                )}
            </div>
        </div>
    );
}

export function VcrDashboardPanel({
    gameId,
    linkedAccountId,
    turn,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
}) {
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [trace, setTrace] = useState<VcrReplayTraceResponse | null>(null);
    const [frameIndex, setFrameIndex] = useState(0);
    const [playing, setPlaying] = useState(false);
    const [speed, setSpeed] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        void getHistoricalCombatEvents(gameId, linkedAccountId, turn)
            .then((response) => {
                if (cancelled) return;
                const ordered = [...response.events].sort(
                    (left, right) => left.vcr_id - right.vcr_id,
                );
                setEvents(ordered);
                setSelectedIndex(0);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR list",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    const selected = events[selectedIndex] ?? null;

    useEffect(() => {
        let cancelled = false;
        setTrace(null);
        setFrameIndex(0);
        setPlaying(false);

        if (selected === null) return () => {
            cancelled = true;
        };

        void getVcrReplayTrace(
            gameId,
            linkedAccountId,
            turn,
            selected.vcr_id,
        )
            .then((response) => {
                if (!cancelled) setTrace(response);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR playback trace",
                    );
                }
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, selected, turn]);

    useEffect(() => {
        if (!playing || trace === null || trace.frames.length === 0) return;

        const timer = window.setInterval(() => {
            setFrameIndex((current) => {
                if (current >= trace.frames.length - 1) {
                    setPlaying(false);
                    return current;
                }
                return Math.min(
                    trace.frames.length - 1,
                    current + Math.max(1, Math.round(speed * 2)),
                );
            });
        }, 50);

        return () => window.clearInterval(timer);
    }, [playing, speed, trace]);

    const frame = trace?.frames[frameIndex] ?? null;

    const currentEvents = useMemo(
        () => frame?.events.map((event) => event.split("_").join(" ")) ?? [],
        [frame],
    );

    return (
        <section className="panel vcr-dashboard-panel">
            <div className="panel-header">
                <div>
                    <h2>Visual Combat Replay</h2>
                    <p>
                        Interactive playback generated from the factual VCR
                        seed and the deterministic NuHost combat engine.
                    </p>
                </div>
            </div>

            {loading ? (
                <div className="loading-card">Loading VCRs…</div>
            ) : error !== null && events.length === 0 ? (
                <div className="error-card">{error}</div>
            ) : events.length === 0 ? (
                <div className="game-dashboard-empty">No VCRs for turn {turn}.</div>
            ) : (
                <div className="vcr-dashboard-layout">
                    <aside className="vcr-event-list">
                        {events.map((event, index) => (
                            <button
                                className={index === selectedIndex ? "is-active" : ""}
                                key={event.vcr_id}
                                onClick={() => setSelectedIndex(index)}
                                type="button"
                            >
                                <strong>VCR #{event.vcr_id}</strong>
                                <span>{eventTitle(event)}</span>
                            </button>
                        ))}
                    </aside>

                    <div className="vcr-player">
                        <div className="vcr-player-heading">
                            <div>
                                <span>Turn {turn}</span>
                                <strong>
                                    {selected === null
                                        ? "VCR"
                                        : `VCR #${selected.vcr_id} · ${eventTitle(selected)}`}
                                </strong>
                            </div>
                            <div className="vcr-nav-buttons">
                                <button
                                    className="secondary-button"
                                    disabled={selectedIndex <= 0}
                                    onClick={() => setSelectedIndex((value) => value - 1)}
                                    type="button"
                                >
                                    Previous
                                </button>
                                <button
                                    className="secondary-button"
                                    disabled={selectedIndex >= events.length - 1}
                                    onClick={() => setSelectedIndex((value) => value + 1)}
                                    type="button"
                                >
                                    Next
                                </button>
                            </div>
                        </div>

                        {trace === null ? (
                            <div className="loading-card">Preparing replay…</div>
                        ) : !trace.supported ? (
                            <div className="error-card">
                                Exact visual replay unavailable: {trace.reason ?? "unsupported combat mode"}
                            </div>
                        ) : frame === null ? (
                            <div className="error-card">Replay contains no frames.</div>
                        ) : (
                            <>
                                <Battlefield
                                    frame={frame}
                                    frameIndex={frameIndex}
                                    frames={trace.frames}
                                />

                                <div className="vcr-status-grid">
                                    <SideStatus label="LEFT" side={frame.left} />
                                    <SideStatus label="RIGHT" side={frame.right} />
                                </div>

                                <div className="vcr-controls">
                                    <button
                                        className="secondary-button"
                                        onClick={() => {
                                            setFrameIndex(0);
                                            setPlaying(false);
                                        }}
                                        type="button"
                                    >
                                        Restart
                                    </button>
                                    <button
                                        className="primary-button"
                                        onClick={() => setPlaying((value) => !value)}
                                        type="button"
                                    >
                                        {playing ? "Pause" : "Play"}
                                    </button>

                                    <div className="vcr-speed-buttons">
                                        {[0.5, 1, 2, 4].map((value) => (
                                            <button
                                                className={speed === value ? "is-active" : ""}
                                                key={value}
                                                onClick={() => setSpeed(value)}
                                                type="button"
                                            >
                                                {value}×
                                            </button>
                                        ))}
                                    </div>

                                    <span>
                                        Cycle {frame.cycle} / {trace.cycles ?? trace.frames.length - 1}
                                    </span>
                                </div>

                                <input
                                    aria-label="VCR timeline"
                                    className="vcr-timeline"
                                    max={Math.max(0, trace.frames.length - 1)}
                                    min={0}
                                    onChange={(event) => {
                                        setPlaying(false);
                                        setFrameIndex(Number(event.target.value));
                                    }}
                                    type="range"
                                    value={frameIndex}
                                />

                                <div className="vcr-event-strip">
                                    {currentEvents.length > 0
                                        ? currentEvents.join(" · ")
                                        : "Combat running"}
                                    {trace.result !== undefined
                                        && frameIndex === trace.frames.length - 1
                                        ? ` · result: ${trace.result.join(", ")}`
                                        : ""}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </section>
    );
}
