import { Container, Graphics, Text } from "pixi.js";

import type { ShipMovementPrediction } from "../../types/movementPrediction";
import { renderY, type MapBounds } from "./mapModel";
import { routeDistance, type MapPoint } from "./navigationAnalysis";


interface RenderPoint {
    x: number;
    y: number;
}


function rendered(point: MapPoint, bounds: MapBounds): RenderPoint {
    return {
        x: point.x,
        y: renderY(point.y, bounds),
    };
}


function pointToward(
    from: MapPoint,
    to: MapPoint,
    maxDistance: number,
): MapPoint {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 0.001 || maxDistance <= 0) return from;
    if (distance <= maxDistance) return to;
    const ratio = maxDistance / distance;
    return {
        x: from.x + dx * ratio,
        y: from.y + dy * ratio,
    };
}


function drawArrowHead(
    world: Container,
    from: RenderPoint,
    to: RenderPoint,
    color: number,
    alpha: number,
) {
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const wing = Math.PI * 0.78;
    const size = 6.5;
    const arrow = new Graphics()
        .moveTo(to.x, to.y)
        .lineTo(
            to.x + Math.cos(angle + wing) * size,
            to.y + Math.sin(angle + wing) * size,
        )
        .moveTo(to.x, to.y)
        .lineTo(
            to.x + Math.cos(angle - wing) * size,
            to.y + Math.sin(angle - wing) * size,
        )
        .stroke({ color, alpha, width: 1.55 });
    world.addChild(arrow);
}


function drawSightingMarker(
    world: Container,
    point: RenderPoint,
    color: number,
) {
    const marker = new Graphics()
        .circle(point.x, point.y, 6.5)
        .stroke({ color, alpha: 0.92, width: 1.2 })
        .moveTo(point.x - 9, point.y)
        .lineTo(point.x + 9, point.y)
        .moveTo(point.x, point.y - 9)
        .lineTo(point.x, point.y + 9)
        .stroke({ color, alpha: 0.72, width: 1 });
    world.addChild(marker);
}


export function drawProvisionalInterceptPrediction({
    world,
    bounds,
    item,
}: {
    world: Container;
    bounds: MapBounds;
    item: ShipMovementPrediction;
}) {
    if (
        item.phase !== "intercept"
        || item.predicted_x !== null
        || item.predicted_y !== null
        || item.start_x === null
        || item.start_y === null
        || item.target_x === null
        || item.target_y === null
        || item.max_distance === null
    ) {
        return;
    }

    const origin: MapPoint = { x: item.start_x, y: item.start_y };
    const sighting: MapPoint = { x: item.target_x, y: item.target_y };
    const endpoint = pointToward(origin, sighting, item.max_distance);
    const movedDistance = routeDistance([origin, endpoint]);
    const sightingDistance = routeDistance([origin, sighting]);

    const from = rendered(origin, bounds);
    const to = rendered(endpoint, bounds);
    const target = rendered(sighting, bounds);
    const color = 0xffc266;

    drawSightingMarker(world, target, 0xf29bff);

    if (movedDistance >= 0.5) {
        const path = new Graphics()
            .moveTo(from.x, from.y)
            .lineTo(to.x, to.y)
            .stroke({ color, alpha: 0.78, width: 1.55 });
        world.addChild(path);
        drawArrowHead(world, from, to, color, 0.88);

        const endpointMarker = new Graphics()
            .circle(to.x, to.y, 4.2)
            .fill({ color, alpha: 0.22 })
            .stroke({ color, alpha: 0.96, width: 1.3 });
        world.addChild(endpointMarker);

        const label = new Text({
            text: (
                `PROVISIONAL · ${movedDistance.toFixed(1)} ly · W${item.warp ?? "—"}`
                + " · target movement unknown"
            ),
            style: {
                fill: color,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 9,
                fontWeight: "700",
                stroke: { color: 0x060a10, width: 3 },
            },
            resolution: 2,
        });
        label.anchor.set(0.5, 1);
        label.position.set(
            (from.x + to.x) / 2,
            (from.y + to.y) / 2 - 5,
        );
        world.addChild(label);
    }

    const sightingLabel = new Text({
        text: (
            `TARGET SIGHTING · #${item.target_ship_id ?? "?"}`
            + ` · ${sightingDistance.toFixed(1)} ly`
        ),
        style: {
            fill: 0xf29bff,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 9,
            fontWeight: "700",
            stroke: { color: 0x060a10, width: 3 },
        },
        resolution: 2,
    });
    sightingLabel.anchor.set(0.5, 0);
    sightingLabel.position.set(target.x, target.y + 10);
    world.addChild(sightingLabel);
}
