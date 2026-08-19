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

type SideName = "left" | "right";

interface PresentationGeometry {
    left: number;
    right: number;
    mapX: (x: number) => number;
}

function sideMarkerClass(side: VcrReplaySideFrame): string {
    return side.is_planet ? "is-planet" : "is-ship";
}

function sideFrame(frame: VcrReplayFrame, side: SideName): VcrReplaySideFrame {
    return side === "left" ? frame.left : frame.right;
}

function oppositeSide(side: SideName): SideName {
    return side === "left" ? "right" : "left";
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

function hullIntegrity(side: VcrReplaySideFrame): number {
    const limit = Math.max(1, side.damage_limit);
    return Math.max(0, Math.min(100, ((limit - side.damage) * 100) / limit));
}

function WeaponChargeRow({
    label,
    slots,
}: {
    label: string;
    slots: number[] | undefined;
}) {
    if (!slots || slots.length === 0) return null;
    return (
        <div className="vcr-weapon-charge-row">
            <span>{label}</span>
            <div className="vcr-weapon-charge-slots">
                {slots.map((charge, index) => (
                    <progress
                        key={`${label}-${index}`}
                        max={100}
                        title={`${label} ${index + 1}: ${Math.min(100, Math.max(0, charge))}%`}
                        value={Math.min(100, Math.max(0, charge))}
                    />
                ))}
            </div>
        </div>
    );
}

function SideStatus({
    label,
    side,
    launching,
}: {
    label: string;
    side: VcrReplaySideFrame;
    launching: boolean;
}) {
    const integrity = hullIntegrity(side);
    return (
        <article className={`vcr-status-card${side.destroyed ? " is-destroyed" : ""}`}>
            <div>
                <span>{label}</span>
                <strong>{side.name ?? `Object #${side.object_id ?? "?"}`}</strong>
            </div>

            <div className="vcr-vital-bars">
                <label className="is-shield">
                    <span>Shield <strong>{side.shield}%</strong></span>
                    <progress max={100} value={Math.max(0, Math.min(100, side.shield))} />
                </label>
                <label className="is-hull">
                    <span>
                        Hull <strong>{integrity.toFixed(0)}%</strong>
                        <small>damage {side.damage}/{side.damage_limit}</small>
                    </span>
                    <progress max={100} value={integrity} />
                </label>
            </div>

            <dl>
                <div><dt>Crew</dt><dd>{side.crew}</dd></div>
                <div><dt>Torps</dt><dd>{side.torpedoes}</dd></div>
                <div><dt>Fighters</dt><dd>{side.fighters}</dd></div>
                <div><dt>Out</dt><dd>{side.fighters_out}</dd></div>
            </dl>

            <div className="vcr-charge-bars">
                <WeaponChargeRow label="Beams" slots={side.beam_slots} />
                <WeaponChargeRow label="Launchers" slots={side.launcher_slots} />
                {side.bay_count > 0 && (
                    <div className={`vcr-fighter-bays${launching ? " is-launching" : ""}`}>
                        <span>Fighter bays</span>
                        <div className="vcr-fighter-bay-pips" title="Classic combat uses a per-cycle launch roll; there is no continuous fighter-bay charge counter.">
                            {Array.from({ length: Math.min(30, side.bay_count) }, (_, index) => (
                                <i key={index} />
                            ))}
                        </div>
                        <small>{side.bay_count} bays · launch roll</small>
                    </div>
                )}
            </div>
        </article>
    );
}

const TORPEDO_PRESENTATION_FRAMES = 12;
const MIN_SHIP_VISUAL_GAP_PERCENT = 28;
const COMBAT_RAW_LEFT = 30;
const COMBAT_RAW_RIGHT = 610;
const STAGE_LEFT = 10;
const STAGE_RIGHT = 90;
const FIGHTER_LANE_COUNT = 19;
const FIGHTER_TOP_MIN = 8;
const FIGHTER_TOP_MAX = 92;

function clamp(value: number, minimum: number, maximum: number): number {
    return Math.max(minimum, Math.min(maximum, value));
}

function stagePercent(x: number): number {
    const progress = (x - COMBAT_RAW_LEFT) / (COMBAT_RAW_RIGHT - COMBAT_RAW_LEFT);
    return STAGE_LEFT + progress * (STAGE_RIGHT - STAGE_LEFT);
}

function presentationGeometry(frame: VcrReplayFrame): PresentationGeometry {
    const rawGap = Math.max(0.01, frame.right.x - frame.left.x);
    let left = stagePercent(frame.left.x);
    let right = stagePercent(frame.right.x);

    if (right - left < MIN_SHIP_VISUAL_GAP_PERCENT) {
        const midpoint = clamp((left + right) / 2, 20, 80);
        left = midpoint - MIN_SHIP_VISUAL_GAP_PERCENT / 2;
        right = midpoint + MIN_SHIP_VISUAL_GAP_PERCENT / 2;
    }

    const visualGap = right - left;
    return {
        left,
        right,
        mapX: (x: number) => {
            const relative = (x - frame.left.x) / rawGap;
            return clamp(left + relative * visualGap, 2, 98);
        },
    };
}

function fighterTop(side: SideName, fighterIndex: number): number {
    const sideOffset = side === "left" ? 0 : 5;
    const lane = (fighterIndex * 7 + sideOffset) % FIGHTER_LANE_COUNT;
    const progress = lane / Math.max(1, FIGHTER_LANE_COUNT - 1);
    return side === "left"
        ? FIGHTER_TOP_MIN + progress * (FIGHTER_TOP_MAX - FIGHTER_TOP_MIN)
        : FIGHTER_TOP_MAX - progress * (FIGHTER_TOP_MAX - FIGHTER_TOP_MIN);
}

function trackById(
    frame: VcrReplayFrame,
    side: SideName,
    fighterId: number | undefined,
): VcrFighterTrack | null {
    if (fighterId === undefined) return null;
    return sideFrame(frame, side).fighter_tracks?.find((track) => track.index === fighterId) ?? null;
}

function nearestTrack(
    frame: VcrReplayFrame,
    side: SideName,
    rawX: number,
): VcrFighterTrack | null {
    const tracks = sideFrame(frame, side).fighter_tracks ?? [];
    let best: VcrFighterTrack | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const track of tracks) {
        const distance = Math.abs(track.x - rawX);
        if (distance < bestDistance) {
            best = track;
            bestDistance = distance;
        }
    }
    return best;
}

function shotLabel(effect: VcrReplayEffect): string | null {
    if (effect.kind === "fighter_attack") {
        return `${effect.source ?? "fighter"} fighter attacks ${effect.target ?? "ship"}`;
    }
    if (effect.kind === "beam_fighter") {
        return `${effect.source ?? "ship"} beam destroys ${effect.target ?? "enemy"} fighter`;
    }
    if (effect.kind === "beam_ship") {
        return `${effect.source ?? "ship"} beam fires`;
    }
    if (effect.kind === "fighter_dogfight_loss") {
        return `dogfight · ${effect.lost_side ?? "unknown"} fighter lost`;
    }
    if (effect.kind === "torpedo_launch") {
        return `${effect.source ?? "ship"} torpedo ${effect.hit === false ? "miss" : "launch"}`;
    }
    return null;
}

function ShotEffectsOverlay({
    effects,
    frame,
    geometry,
}: {
    effects: VcrReplayEffect[];
    frame: VcrReplayFrame;
    geometry: PresentationGeometry;
}) {
    const lines: Array<{
        key: string;
        className: string;
        x1: number;
        y1: number;
        x2: number;
        y2: number;
    }> = [];

    effects.forEach((effect, index) => {
        if (effect.kind === "beam_ship" && effect.source !== undefined) {
            const source = effect.source;
            const target = effect.target ?? oppositeSide(source);
            lines.push({
                key: `beam-ship-${index}`,
                className: `vcr-beam-shot is-${source}`,
                x1: geometry.mapX(effect.source_x ?? sideFrame(frame, source).x),
                y1: 50,
                x2: geometry.mapX(effect.target_x ?? sideFrame(frame, target).x),
                y2: 50,
            });
            return;
        }

        if (effect.kind === "beam_fighter" && effect.source !== undefined) {
            const source = effect.source;
            const target = effect.target ?? oppositeSide(source);
            const targetTrack = trackById(frame, target, effect.fighter_id);
            lines.push({
                key: `beam-fighter-${index}`,
                className: `vcr-beam-shot is-${source} is-fighter-target`,
                x1: geometry.mapX(effect.source_x ?? sideFrame(frame, source).x),
                y1: 50,
                x2: geometry.mapX(
                    targetTrack?.x
                    ?? effect.target_x
                    ?? sideFrame(frame, target).x,
                ),
                y2: fighterTop(target, effect.fighter_id ?? targetTrack?.index ?? 0),
            });
            return;
        }

        if (effect.kind === "fighter_attack" && effect.source !== undefined) {
            const source = effect.source;
            const target = effect.target ?? oppositeSide(source);
            const sourceTrack = trackById(frame, source, effect.fighter_id);
            lines.push({
                key: `fighter-ship-${index}`,
                className: `vcr-fighter-shot is-${source}`,
                x1: geometry.mapX(
                    sourceTrack?.x
                    ?? effect.source_x
                    ?? sideFrame(frame, source).x,
                ),
                y1: fighterTop(source, effect.fighter_id ?? sourceTrack?.index ?? 0),
                x2: geometry.mapX(effect.target_x ?? sideFrame(frame, target).x),
                y2: 50,
            });
            return;
        }

        if (effect.kind === "fighter_dogfight_loss" && effect.lost_side !== undefined) {
            const target = effect.lost_side;
            const source = oppositeSide(target);
            const rawX = effect.x ?? sideFrame(frame, target).x;
            const sourceTrack = nearestTrack(frame, source, rawX);
            const targetIndex = effect.fighter_id ?? 0;
            const sourceIndex = sourceTrack?.index ?? targetIndex;
            const targetX = geometry.mapX(rawX);
            let sourceX = geometry.mapX(sourceTrack?.x ?? rawX);
            if (Math.abs(sourceX - targetX) < 0.8) {
                sourceX += source === "left" ? -1.2 : 1.2;
            }
            lines.push({
                key: `fighter-dogfight-${index}`,
                className: `vcr-fighter-shot is-${source} is-dogfight`,
                x1: sourceX,
                y1: fighterTop(source, sourceIndex),
                x2: targetX,
                y2: fighterTop(target, targetIndex),
            });
        }
    });

    if (lines.length === 0) return null;

    return (
        <svg
            aria-hidden="true"
            className="vcr-shot-overlay"
            preserveAspectRatio="none"
            viewBox="0 0 100 100"
        >
            {lines.map((line) => (
                <line
                    className={line.className}
                    key={line.key}
                    x1={line.x1}
                    x2={line.x2}
                    y1={line.y1}
                    y2={line.y2}
                />
            ))}
        </svg>
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
        side: SideName;
        x: number;
        y: number;
        hit: boolean;
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
                ?? sideFrame(launchFrame, effect.source).x;
            const targetSide = effect.target ?? oppositeSide(effect.source);
            const targetRaw = effect.target_x
                ?? sideFrame(launchFrame, targetSide).x;
            const count = Math.max(1, effect.count ?? 1);
            for (let projectile = 0; projectile < Math.min(4, count); projectile += 1) {
                const rawX = sourceRaw + (targetRaw - sourceRaw) * progress;
                const laneSeed = (launchIndex * 11 + effectIndex * 7 + projectile * 3) % 7;
                const launchY = 38 + laneSeed * 4;
                const missUp = (launchIndex + effectIndex + projectile) % 2 === 0;
                const hit = effect.hit !== false;
                const targetY = hit ? 50 : (missUp ? 10 : 90);
                const bend = Math.sin(progress * Math.PI) * (missUp ? -4 : 4);
                torpedoes.push({
                    key: `${launchIndex}-${effectIndex}-${projectile}`,
                    side: effect.source,
                    x: geometry.mapX(rawX),
                    y: launchY + (targetY - launchY) * progress + bend,
                    hit,
                });
            }
        }
    }

    const fighterTracks: Array<{
        side: SideName;
        track: VcrFighterTrack;
    }> = [
        ...(frame.left.fighter_tracks ?? []).map((track) => ({ side: "left" as const, track })),
        ...(frame.right.fighter_tracks ?? []).map((track) => ({ side: "right" as const, track })),
    ];

    const leftLaunching = effects.some((effect) => effect.kind === "fighter_launch" && effect.source === "left");
    const rightLaunching = effects.some((effect) => effect.kind === "fighter_launch" && effect.source === "right");

    return (
        <div className="vcr-battlefield">
            <div className="vcr-range-line" />

            <ShotEffectsOverlay effects={effects} frame={frame} geometry={geometry} />

            {torpedoes.map((torpedo) => (
                <span
                    aria-hidden="true"
                    className={`vcr-torpedo-projectile is-${torpedo.side}${torpedo.hit ? " is-hit-course" : " is-miss-course"}`}
                    key={torpedo.key}
                    style={{
                        left: `${torpedo.x}%`,
                        top: `${torpedo.y}%`,
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
                        top: `${fighterTop(side, track.index)}%`,
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
                        style={{
                            left: `${geometry.mapX(effect.x ?? 320)}%`,
                            top: `${fighterTop(effect.lost_side ?? "left", effect.fighter_id ?? 0)}%`,
                        }}
                    >×</span>
                );
            })}

            <div
                className={`vcr-combat-object ${sideMarkerClass(frame.left)}${hitLeft ? " is-hit" : ""}${frame.left.destroyed ? " is-destroyed" : ""}`}
                style={{ left: `${geometry.left}%` }}
            >
                <div className="vcr-combat-visual">
                    <CombatObjectArtwork facing="right" side={frame.left} />
                    {frame.left.destroyed && <span aria-hidden="true" className="vcr-destruction-burst" />}
                </div>
                <div className="vcr-combat-label">
                    <strong>{frame.left.name ?? `#${frame.left.object_id ?? "?"}`}</strong>
                    {frame.left.fighters_out > 0 && <small>{frame.left.fighters_out} fighters out</small>}
                    {frame.left.destroyed && <small className="is-destroyed-label">destroyed</small>}
                </div>
            </div>
            <div
                className={`vcr-combat-object ${sideMarkerClass(frame.right)}${hitRight ? " is-hit" : ""}${frame.right.destroyed ? " is-destroyed" : ""}`}
                style={{ left: `${geometry.right}%` }}
            >
                <div className="vcr-combat-visual">
                    <CombatObjectArtwork facing="left" side={frame.right} />
                    {frame.right.destroyed && <span aria-hidden="true" className="vcr-destruction-burst" />}
                </div>
                <div className="vcr-combat-label">
                    <strong>{frame.right.name ?? `#${frame.right.object_id ?? "?"}`}</strong>
                    {frame.right.fighters_out > 0 && <small>{frame.right.fighters_out} fighters out</small>}
                    {frame.right.destroyed && <small className="is-destroyed-label">destroyed</small>}
                </div>
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
                return Math.min(frames.length - 1, current + 1);
            });
        }, Math.max(12, Math.round(50 / speed)));
        return () => window.clearInterval(timer);
    }, [frames, playing, speed]);

    const frame = frames[frameIndex] ?? null;
    const currentEvents = useMemo(() => {
        if (frame === null) return [];
        const labels = [
            ...frame.events.map((event) => event.split("_").join(" ")),
            ...(frame.effects ?? [])
                .map(shotLabel)
                .filter((label): label is string => label !== null),
        ];
        return [...new Set(labels)];
    }, [frame]);

    if (frame === null) return <div className="error-card">Replay contains no frames.</div>;

    const leftLaunching = (frame.effects ?? []).some(
        (effect) => effect.kind === "fighter_launch" && effect.source === "left",
    );
    const rightLaunching = (frame.effects ?? []).some(
        (effect) => effect.kind === "fighter_launch" && effect.source === "right",
    );

    return (
        <div className="vcr-player battle-sim-replay-player">
            {title && (
                <div className="vcr-player-heading">
                    <div><span>SIMULATED VCR</span><strong>{title}</strong></div>
                </div>
            )}
            <Battlefield frame={frame} frameIndex={frameIndex} frames={frames} />
            <div className="vcr-status-grid">
                <SideStatus label="LEFT" launching={leftLaunching} side={frame.left} />
                <SideStatus label="RIGHT" launching={rightLaunching} side={frame.right} />
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
                onChange={(event) => {
                    setFrameIndex(Number(event.target.value));
                    setPlaying(false);
                }}
                type="range"
                value={frameIndex}
            />
            <div className="vcr-event-strip">
                {currentEvents.length > 0
                    ? currentEvents.join(" · ")
                    : frameIndex >= frames.length - 1 && result && result.length > 0
                        ? result.map((item) => item.split("_").join(" ")).join(" · ")
                        : "No weapon event this cycle"}
            </div>
        </div>
    );
}