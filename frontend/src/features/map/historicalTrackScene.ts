import { Container, Graphics, Text } from "pixi.js";
import type {
    HistoricalShipTrack,
    HistoricalShipTrackPoint,
} from "../../types/history";
import { raceVisual } from "../../lib/races";
import { renderY, type MapBounds, type SelectedEntity } from "./mapModel";

export type ShipTrackMode = "off" | "selected" | "all";

const UNKNOWN_TRACK_COLOR = 0x70829a;

function trackColor(ownerId: number | null): number {
    return raceVisual(ownerId)?.color ?? UNKNOWN_TRACK_COLOR;
}

function fadedAlpha(
    baseAlpha: number,
    turn: number,
    throughTurn: number,
    fadePerTurn: number,
    minimumAlpha: number,
): number {
    const age = Math.max(throughTurn - turn, 0);
    const retainedPerTurn = Math.min(
        Math.max(1 - fadePerTurn, 0),
        1,
    );
    const alpha = baseAlpha * Math.pow(retainedPerTurn, age);
    return Math.min(Math.max(alpha, minimumAlpha), 1);
}

function drawTrackPoint({
    world,
    point,
    bounds,
    color,
    selectedTrack,
    throughTurn,
    fadePerTurn,
}: {
    world: Container;
    point: HistoricalShipTrackPoint;
    bounds: MapBounds;
    color: number;
    selectedTrack: boolean;
    throughTurn: number;
    fadePerTurn: number;
}) {
    const x = point.x;
    const y = renderY(point.y, bounds);
    const isCombat = point.evidence === "combat";
    const alpha = fadedAlpha(
        selectedTrack ? 0.98 : isCombat ? 0.82 : 0.45,
        point.turn,
        throughTurn,
        fadePerTurn,
        selectedTrack ? 0.1 : isCombat ? 0.16 : 0.03,
    );

    if (isCombat) {
        const marker = new Graphics()
            .circle(0, 0, selectedTrack ? 5.2 : 4.4)
            .stroke({
                color,
                width: selectedTrack ? 1.8 : 1.25,
                alpha,
            })
            .moveTo(-3.2, -3.2)
            .lineTo(3.2, 3.2)
            .moveTo(3.2, -3.2)
            .lineTo(-3.2, 3.2)
            .stroke({
                color: 0xffd4d4,
                width: selectedTrack ? 1.5 : 1.1,
                alpha: Math.min(alpha + 0.12, 1),
            });
        marker.position.set(x, y);
        world.addChild(marker);
    } else {
        const marker = new Graphics()
            .circle(0, 0, selectedTrack ? 2.8 : 1.45)
            .fill({ color, alpha });
        if (selectedTrack) {
            marker.stroke({
                color: 0xffffff,
                width: 0.7,
                alpha: fadedAlpha(
                    0.76,
                    point.turn,
                    throughTurn,
                    fadePerTurn,
                    0.08,
                ),
            });
        }
        marker.position.set(x, y);
        world.addChild(marker);
    }

    if (!selectedTrack) return;

    const labelAlpha = fadedAlpha(
        1,
        point.turn,
        throughTurn,
        fadePerTurn,
        0.18,
    );
    const suffix = point.evidence === "combat"
        ? ` · combat${point.combat_vcr_id !== null ? ` #${point.combat_vcr_id}` : ""}`
        : point.gap_from_previous
            ? " · reacquired"
            : "";
    const label = new Text({
        text: `T${point.turn}${suffix}`,
        style: {
            fill: point.evidence === "combat"
                ? 0xffd1d1
                : point.gap_from_previous
                    ? 0xffcf7d
                    : 0xcbd8e8,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 9,
            stroke: { color: 0x060a10, width: 3 },
        },
        resolution: 2,
    });
    label.alpha = labelAlpha;
    label.position.set(x + 5, y - 12);
    world.addChild(label);
}

export function drawHistoricalShipTracks({
    world,
    tracks,
    bounds,
    selected,
    mode,
    throughTurn,
    lookbackTurns,
    fadePerTurn,
}: {
    world: Container;
    tracks: HistoricalShipTrack[];
    bounds: MapBounds;
    selected: SelectedEntity | null;
    mode: ShipTrackMode;
    throughTurn: number;
    lookbackTurns: number | null;
    fadePerTurn: number;
}) {
    if (mode === "off") return;

    const selectedShipId = selected?.kind === "ship"
        ? selected.value.ship_id
        : null;
    const minimumTurn = lookbackTurns === null
        ? Number.NEGATIVE_INFINITY
        : throughTurn - Math.max(lookbackTurns, 0);

    for (const track of tracks) {
        const selectedTrack = selectedShipId === track.ship_id;
        if (mode === "selected" && !selectedTrack) continue;

        const points = track.points.filter(
            (point) => point.turn >= minimumTurn && point.turn <= throughTurn,
        );
        if (points.length === 0) continue;

        const color = trackColor(track.owner_id);

        for (let index = 1; index < points.length; index += 1) {
            const previous = points[index - 1];
            const current = points[index];

            // Never draw an invented straight path across turns in which the
            // ship was not observed. Breadcrumbs on both sides make the gap
            // visible without asserting how the ship travelled through it.
            if (current.gap_from_previous) continue;

            const line = new Graphics()
                .moveTo(previous.x, renderY(previous.y, bounds))
                .lineTo(current.x, renderY(current.y, bounds))
                .stroke({
                    color,
                    width: selectedTrack ? 2.5 : 1.15,
                    alpha: fadedAlpha(
                        selectedTrack ? 0.94 : 0.34,
                        current.turn,
                        throughTurn,
                        fadePerTurn,
                        selectedTrack ? 0.08 : 0.025,
                    ),
                });
            world.addChild(line);
        }

        for (const point of points) {
            drawTrackPoint({
                world,
                point,
                bounds,
                color,
                selectedTrack,
                throughTurn,
                fadePerTurn,
            });
        }
    }
}
