import { Container, Graphics, Text } from "pixi.js";
import type { HistoricalShipTrack } from "../../types/history";
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
            const marker = new Graphics()
                .circle(0, 0, selectedTrack ? 2.8 : 1.45)
                .fill({
                    color,
                    alpha: fadedAlpha(
                        selectedTrack ? 0.98 : 0.45,
                        point.turn,
                        throughTurn,
                        fadePerTurn,
                        selectedTrack ? 0.1 : 0.03,
                    ),
                });
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
            marker.position.set(point.x, renderY(point.y, bounds));
            world.addChild(marker);

            if (!selectedTrack) continue;

            const labelAlpha = fadedAlpha(
                1,
                point.turn,
                throughTurn,
                fadePerTurn,
                0.18,
            );
            const label = new Text({
                text: point.gap_from_previous
                    ? `T${point.turn} · reacquired`
                    : `T${point.turn}`,
                style: {
                    fill: point.gap_from_previous ? 0xffcf7d : 0xcbd8e8,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: 9,
                    stroke: {
                        color: 0x060a10,
                        width: 3,
                    },
                },
                resolution: 2,
            });
            label.alpha = labelAlpha;
            label.position.set(point.x + 4, renderY(point.y, bounds) - 11);
            world.addChild(label);
        }
    }
}
