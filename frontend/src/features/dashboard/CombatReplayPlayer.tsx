import { useEffect, useMemo, useState } from "react";

import type {
    VcrFighterTrack,
    VcrReplayEffect,
    VcrReplayFrame,
    VcrReplaySideFrame,
} from "../../api/vcrReplay";
import {
    privateHullAssetUrl,
    privatePlanetAssetUrl,
} from "../../lib/privateAssets";
import "./vcr-hull-artwork.css";

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
        if (assetUrl === null) return () => { cancelled = true; };

        void (async () => {
            for (let attempt = 1; attempt <= 3; attempt += 1) {
                try {
                    const response = await fetch(assetUrl, {
                        credentials: "same-origin",
                        cache: "force-cache",
                        headers: { Accept: "image/png" },
                    });
                    if (!response.ok) throw new Error(`Artwork HTTP ${response.status}`);
                    await response.blob();
                    if (!cancelled) setReady(true);
                    return;
                } catch {
                    if (attempt < 3) {
                        await new Promise((resolve) => window.setTimeout(resolve, attempt * 650));
                    }
                }
            }
        })();
        return () => { cancelled = true; };
    }, [assetUrl]);

    if (assetUrl === null) return <span className="vcr-object-marker" />;

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
            <span className="vcr-object-marker" hidden={ready && loaded} />
        </span>
    );
}

function SideStatus({ label, side }: { label: string; side: VcrReplaySideFrame }) {
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

const TORPEDO_PRESENTATION_FRAMES = 12;
const MIN_SHIP_VISUAL_GAP_PERCENT = 22;

function combatPercent(x: number): number {
    return Math.max(4, Math.min(96, (x / 640) * 100));
}

function presentationGeometry(frame: VcrReplayFrame): {
    left: number;
    right: number;
    mapX: (x: number) => number;
} {
    const rawLeftPercent = combatPercent(frame.left.x);
    const rawRightPercent = combatPercent(frame.right.x);
    const rawGap = Math.max(0.01, rawRightPercent - rawLeftPercent);
    let left = rawLeftPercent;
    let right = rawRightPercent;

    // Combat coordinates legitimately close to 30 units, but the original Nu
    // artwork is much wider than 30/640 of the viewport. Keep simulation
    // coordinates untouched and expand only their presentation space so large
    // hull sprites never sit on top of each other.
    if (right - left < MIN_SHIP_VISUAL_GAP_PERCENT) {
        const midpoint = (left + right) / 2;
        left = midpoint - MIN_SHIP_VISUAL_GAP_PERCENT / 2;
        right = midpoint + MIN_SHIP_VISUAL_GAP_PERCENT / 2;
        if (left < 5) {
            right += 5 - left;
            left = 5;
        }
        if (right > 95) {
            left -= right - 95;
            right = 95;
        }
    }

    const visualGap = right - left;
    return {
        left,
        right,
        mapX: (x: number) => {
            const raw = combatPercent(x);
            const relative = (raw - rawLeftPercent) / rawGap;
            return Math.max(2, Math.min(98, left + relative * visualGap));
        },
    };
}

function fighterTop(side: "left" | "right", track: VcrFighterTrack): number {
    const lane = track.index % 7;
    return side === "left"
        ? 35 + lane * 3.2
        : 65 - lane * 3.2;
}

function lineStyle(
    start: number,
    end: number,
    top: number,
): React.CSSProperties {
    return {
        left: `${Math.min(start, end)}%`,
        width: `${Math.max(0.6, Math.abs(end - start))}%`,
        top: `${top}%`,
    };
}

function BeamEffect({
    effect,
    frame,
    mapX,
    index,
}: {
    effect: VcrReplayEffect;
    frame: VcrReplayFrame;
    mapX: (x: number) => number;
    index: number;
}) {
    if (
        effect.kind !== "beam_ship"
        && effect.kind !== "beam_fighter"
        && effect.kind !== "fighter_attack"
    ) return null;

    const sourceSide = effect.source === "right" ? frame.right : frame.left;
    const targetSide = effect.target === "left" ? frame.left : frame.right;
    const sourceRaw = effect.source_x ?? sourceSide.x;
    const targetRaw = effect.target_x ?? targetSide.x;
    const source = mapX(sourceRaw);
    const target = mapX(targetRaw);
    const top = effect.kind === "fighter_attack"
        ? (effect.source === "left" ? 45 : 55)
        : 50 + ((index % 3) - 1) * 2.2;

    return (
        <span
            aria-hidden="true"
            className={
                effect.kind === "fighter_attack"
                    ? "vcr-fighter-shot"
                    : `vcr-beam-shot is-${effect.source ?? "left"}`
            }
            style={lineStyle(source, target, top)}
        />
    );
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
    const geometry = presentationGeometry(frame);
    const hitLeft = frame.events.includes("left_hit");
    const hitRight = frame.events.includes("right_hit");
    const effects = frame.effects ?? [];

    const torpedoes: Array<{
        key: string;
        side: "left" | "right";
        x: number;
        lane: number;
    }> = [];

    for (
        let launchIndex = frameIndex;
        launchIndex >= Math.max(0, frameIndex - TORPEDO_PRESENTATION_FRAMES + 1);
        launchIndex -= 1
    ) {
        const launchFrame = frames[launchIndex];
        for (const [effectIndex, effect] of (launchFrame.effects ?? []).entries()) {
            if (effect.kind !== "torpedo_launch" || effect.source === undefined) continue;
            const age = frameIndex - launchIndex;
            const progress = Math.min(1, (age + 1) / TORPEDO_PRESENTATION_FRAMES);
            const sourceRaw = effect.source_x
                ?? (effect.source === "left" ? launchFrame.left.x : launchFrame.right.x);
            const targetRaw = effect.target_x
                ?? (effect.source === "left" ? launchFrame.right.x : launchFrame.left.x);
            const count = Math.max(1, effect.count ?? 1);
            for (let projectile = 0; projectile < Math.min(4, count); projectile += 1) {
                const rawX = sourceRaw + (targetRaw - sourceRaw) * progress;
                torpedoes.push({
                    key: `${launchIndex}-${effectIndex}-${projectile}`,
                    side: effect.source,
                    x: geometry.mapX(rawX),
                    lane: projectile,
                });
            }
        }
    }

    const fighterTracks: Array<{
        side: "left" | "right";
        track: VcrFighterTrack;
    }> = [
        ...(frame.left.fighter_tracks ?? []).map((track) => ({ side: "left" as const, track })),
        ...(frame.right.fighter_tracks ?? []).map((track) => ({ side: "right" as const, track })),
    ];

    return (
        <div className="vcr-battlefield">
            <div className="vcr-range-line" />

            {effects.map((effect, index) => (
                <BeamEffect
                    effect={effect}
                    frame={frame}
                    index={index}
                    key={`beam-${index}-${effect.kind}`}
                    mapX={geometry.mapX}
                />
            ))}

            {torpedoes.map((torpedo) => (
                <span
                    aria-hidden="true"
                    className={`vcr-torpedo-projectile is-${torpedo.side}`}
                    key={torpedo.key}
                    style={{
                        left: `${torpedo.x}%`,
                        top: `${48 + (torpedo.lane - 1.5) * 2}%`,
                    }}
                >
                    <span />
                </span>
            ))}

            {fighterTracks.map(({ side, track }) => (
                <span
                    aria-hidden="true"
                    className={`vcr-fighter is-${side}${track.status === 2 ? " is-returning" : ""}`}
                    key={`${side}-fighter-${track.index}`}
                    style={{
                        left: `${geometry.mapX(track.x)}%`,
                        top: `${fighterTop(side, track)}%`,
                    }}
                    title={`${side} fighter ${track.index + 1}`}
                />
            ))}

            {effects.map((effect, index) => {
                if (effect.kind !== "fighter_dogfight_loss") return null;
                return (
                    <span
                        aria-hidden="true"
                        className="vcr-dogfight-flash"
                        key={`dogfight-${index}`}
                        style={{ left: `${geometry.mapX(effect.x ?? 320)}%` }}
                    >×</span>
                );
            })}

            <div
                className={`vcr-combat-object ${sideMarkerClass(frame.left)}${hitLeft ? " is-hit" : ""}`}
                style={{ left: `${geometry.left}%` }}
            >
                <CombatObjectArtwork facing="right" side={frame.left} />
                <strong>{frame.left.name ?? `#${frame.left.object_id ?? "?"}`}</strong>
                {frame.left.fighters_out > 0 && <small>{frame.left.fighters_out} fighters out</small>}
            </div>
            <div
                className={`vcr-combat-object ${sideMarkerClass(frame.right)}${hitRight ? " is-hit" : ""}`}
                style={{ left: `${geometry.right}%` }}
            >
                <CombatObjectArtwork facing="left" side={frame.right} />
                <strong>{frame.right.name ?? `#${frame.right.object_id ?? "?"}`}</strong>
                {frame.right.fighters_out > 0 && <small>{frame.right.fighters_out} fighters out</small>}
            </div>
        </div>
    );
}

export function CombatReplayPlayer({
    frames,
    cycles,
    result,
    title,
    autoPlay = true,
}: {
    frames: VcrReplayFrame[];
    cycles?: number;
    result?: string[];
    title?: string;
    autoPlay?: boolean;
}) {
    const [frameIndex, setFrameIndex] = useState(0);
    const [playing, setPlaying] = useState(autoPlay);
    const [speed, setSpeed] = useState(1);

    useEffect(() => {
        setFrameIndex(0);
        setPlaying(autoPlay);
    }, [autoPlay, frames]);

    useEffect(() => {
        if (!playing || frames.length === 0) return;
        const timer = window.setInterval(() => {
            setFrameIndex((current) => {
                if (current >= frames.length - 1) {
                    setPlaying(false);
                    return current;
                }
                return Math.min(frames.length - 1, current + Math.max(1, Math.round(speed * 2)));
            });
        }, 50);
        return () => window.clearInterval(timer);
    }, [frames, playing, speed]);

    const frame = frames[frameIndex] ?? null;
    const currentEvents = useMemo(
        () => frame?.events.map((event) => event.split("_").join(" ")) ?? [],
        [frame],
    );

    if (frame === null) return <div className="error-card">Replay contains no frames.</div>;

    return (
        <div className="vcr-player battle-sim-replay-player">
            {title && (
                <div className="vcr-player-heading">
                    <div><span>SIMULATED VCR</span><strong>{title}</strong></div>
                </div>
            )}
            <Battlefield frame={frame} frameIndex={frameIndex} frames={frames} />
            <div className="vcr-status-grid">
                <SideStatus label="LEFT" side={frame.left} />
                <SideStatus label="RIGHT" side={frame.right} />
            </div>
            <div className="vcr-controls">
                <button
                    className="secondary-button"
                    onClick={() => { setFrameIndex(0); setPlaying(false); }}
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
                <span>Cycle {frame.cycle} / {cycles ?? frames.length - 1}</span>
            </div>
            <input
                aria-label="Simulated combat timeline"
                className="vcr-timeline"
                max={Math.max(0, frames.length - 1)}
                min={0}
                onChange={(event) => { setPlaying(false); setFrameIndex(Number(event.target.value)); }}
                type="range"
                value={frameIndex}
            />
            <div className="vcr-event-strip">
                {currentEvents.length > 0 ? currentEvents.join(" · ") : "Combat running"}
                {result !== undefined && frameIndex === frames.length - 1
                    ? ` · result: ${result.join(", ").replaceAll("_", " ")}`
                    : ""}
            </div>
        </div>
    );
}
