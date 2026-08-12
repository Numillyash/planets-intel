import { Container, Graphics, Text } from "pixi.js";
import type { HistoricalShipTrack } from "../../types/history";
import { raceVisual } from "../../lib/races";
import { renderY, type MapBounds, type SelectedEntity } from "./mapModel";

export type ShipTrackMode = "off" | "selected" | "all";

const UNKNOWN_TRACK_COLOR = 0x70829a;

function trackColor(ownerId: number | null): number {
    return raceVisual(ownerId)?.color ?? UNKNOWN_TRACK_COLOR;
}

export function drawHistoricalShipTracks({
    world,
    tracks,
    bounds,
    selected,
    mode,
}: {
    world: Container;
    tracks: HistoricalShipTrack[];
    bounds: MapBounds;
    selected: SelectedEntity | null;
    mode: ShipTrackMode;
}) {
    if (mode === "off") return;

    const selectedShipId = selected?.kind === "ship"
        ? selected.value.ship_id
        : null;

    for (const track of tracks) {
        const selectedTrack = selectedShipId === track.ship_id;
        if (mode === "selected" && !selectedTrack) continue;
        if (track.points.length === 0) continue;

        const color = trackColor(track.owner_id);
        const line = new Graphics();
        let hasSegment = false;

        for (let index = 1; index < track.points.length; index += 1) {
            const previous = track.points[index - 1];
            const current = track.points[index];

            // Never draw an invented straight path across turns in which the
            // ship was not observed. Breadcrumbs on both sides make the gap
            // visible without asserting how the ship travelled through it.
            if (current.gap_from_previous) continue;

            line
                .moveTo(previous.x, renderY(previous.y, bounds))
                .lineTo(current.x, renderY(current.y, bounds));
            hasSegment = true;
        }

        if (hasSegment) {
            line.stroke({
                color,
                width: selectedTrack ? 2.5 : 1.15,
                alpha: selectedTrack ? 0.94 : 0.3,
            });
            world.addChild(line);
        }

        for (const point of track.points) {
            const marker = new Graphics()
                .circle(0, 0, selectedTrack ? 2.8 : 1.45)
                .fill({
                    color,
                    alpha: selectedTrack ? 0.98 : 0.4,
                });
            if (selectedTrack) {
                marker.stroke({
                    color: 0xffffff,
                    width: 0.7,
                    alpha: 0.76,
                });
            }
            marker.position.set(point.x, renderY(point.y, bounds));
            world.addChild(marker);

            if (!selectedTrack) continue;

            const label = new Text({
                text: point.gap_from_previous
                    ? `T${point.turn} · reacquired`
                    : `T${point.turn}`,
                style: {
                    fill: point.gap_from_previous ? 0xffcf7d : 0xcbd8e8,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: 9,
                    stroke: { color: 0x060a10, width: 3 },
                },
                resolution: 2,
            });
            label.position.set(point.x + 4, renderY(point.y, bounds) - 11);
            world.addChild(label);
        }
    }
}
