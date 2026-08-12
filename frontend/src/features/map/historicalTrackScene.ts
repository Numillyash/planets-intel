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
        if (track.points.length < 2) continue;

        const color = trackColor(track.owner_id);
        const line = new Graphics();
        let hasSegment = false;

        for (let index = 1; index < track.points.length; index += 1) {
            const previous = track.points[index - 1];
            const current = track.points[index];

            // Never draw an invented straight path across turns in which the
            // ship was not observed. The gap remains visibly disconnected.
            if (current.gap_from_previous) continue;

            line
                .moveTo(previous.x, renderY(previous.y, bounds))
                .lineTo(current.x, renderY(current.y, bounds));
            hasSegment = true;
        }

        if (hasSegment) {
            line.stroke({
                color,
                width: selectedTrack ? 2.4 : 1,
                alpha: selectedTrack ? 0.92 : 0.16,
            });
            world.addChild(line);
        }

        if (selectedTrack) {
            for (const point of track.points) {
                const marker = new Graphics()
                    .circle(0, 0, 2.7)
                    .fill({ color, alpha: 0.96 })
                    .stroke({ color: 0xffffff, width: 0.7, alpha: 0.75 });
                marker.position.set(point.x, renderY(point.y, bounds));
                world.addChild(marker);

                const label = new Text({
                    text: `T${point.turn}`,
                    style: {
                        fill: 0xcbd8e8,
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
}
