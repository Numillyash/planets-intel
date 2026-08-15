import { Container, Graphics, Text } from "pixi.js";

import type { ShipMovementPrediction } from "../../types/movementPrediction";
import { renderY, type MapBounds } from "./mapModel";


interface RenderPoint {
    x: number;
    y: number;
}


function rendered(
    x: number,
    y: number,
    bounds: MapBounds,
): RenderPoint {
    return { x, y: renderY(y, bounds) };
}


function drawDashedSegment(
    graphics: Graphics,
    from: RenderPoint,
    to: RenderPoint,
    dashLength = 5,
    gapLength = 4,
) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy);
    if (length < 0.001) return;

    const ux = dx / length;
    const uy = dy / length;
    const period = dashLength + gapLength;
    for (let distance = 0; distance < length; distance += period) {
        const endDistance = Math.min(distance + dashLength, length);
        graphics
            .moveTo(from.x + ux * distance, from.y + uy * distance)
            .lineTo(from.x + ux * endDistance, from.y + uy * endDistance);
    }
}


export function drawWarpWellPrediction({
    world,
    bounds,
    item,
}: {
    world: Container;
    bounds: MapBounds;
    item: ShipMovementPrediction;
}): boolean {
    if (
        item.warp_well_status !== "captured"
        || item.start_x === null
        || item.start_y === null
        || item.pre_well_x === null
        || item.pre_well_y === null
        || item.predicted_x === null
        || item.predicted_y === null
    ) {
        return false;
    }

    const from = rendered(item.start_x, item.start_y, bounds);
    const preWell = rendered(item.pre_well_x, item.pre_well_y, bounds);
    const final = rendered(item.predicted_x, item.predicted_y, bounds);
    const moveColor = item.phase === "intercept" ? 0xffa7ff : 0x76f0c0;
    const wellColor = 0xffd36a;

    const flight = new Graphics()
        .moveTo(from.x, from.y)
        .lineTo(preWell.x, preWell.y)
        .stroke({ color: moveColor, alpha: item.certain ? 0.88 : 0.55, width: 1.65 });
    world.addChild(flight);

    const preWellMarker = new Graphics()
        .circle(preWell.x, preWell.y, 3.2)
        .fill({ color: moveColor, alpha: 0.16 })
        .stroke({ color: moveColor, alpha: 0.95, width: 1.1 });
    world.addChild(preWellMarker);

    const pull = new Graphics();
    drawDashedSegment(pull, preWell, final);
    pull.stroke({ color: wellColor, alpha: 0.95, width: 1.35 });
    world.addChild(pull);

    const finalMarker = new Graphics()
        .circle(final.x, final.y, 5.0)
        .stroke({ color: wellColor, alpha: 0.95, width: 1.45 })
        .circle(final.x, final.y, 2.0)
        .fill({ color: wellColor, alpha: 0.55 });
    world.addChild(finalMarker);

    const moved = item.moved_distance ?? 0;
    const flightLabel = new Text({
        text: `MOVE ${moved.toFixed(1)} · W${item.warp ?? "—"}`,
        style: {
            fill: moveColor,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 7.5,
            fontWeight: "700",
            stroke: { color: 0x060a10, width: 2.4 },
        },
        resolution: 2,
    });
    flightLabel.anchor.set(0.5, 1);
    flightLabel.position.set(
        (from.x + preWell.x) / 2,
        (from.y + preWell.y) / 2 - 3,
    );
    world.addChild(flightLabel);

    const planetLabel = item.warp_well_planet_name
        ?? (item.warp_well_planet_id !== null
            ? `#${item.warp_well_planet_id}`
            : "planet");
    const pullDistance = item.warp_well_pull_distance;
    const wellLabel = new Text({
        text: (
            `WELL → ${planetLabel}`
            + (pullDistance !== null ? ` · ${pullDistance.toFixed(1)} ly` : "")
        ),
        style: {
            fill: wellColor,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 7.5,
            fontWeight: "700",
            stroke: { color: 0x060a10, width: 2.4 },
        },
        resolution: 2,
    });
    wellLabel.anchor.set(0.5, 0);
    wellLabel.position.set(
        (preWell.x + final.x) / 2,
        (preWell.y + final.y) / 2 + 4,
    );
    world.addChild(wellLabel);

    return true;
}
