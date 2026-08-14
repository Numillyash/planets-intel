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


function drawDashedCircle(
    world: Container,
    center: RenderPoint,
    radius: number,
    color: number,
) {
    if (radius < 0.5) return;

    const circumference = Math.PI * 2 * radius;
    const dashLength = 8;
    const gapLength = 6;
    const period = dashLength + gapLength;
    const count = Math.max(Math.floor(circumference / period), 18);
    const angularPeriod = (Math.PI * 2) / count;
    const dashFraction = dashLength / period;
    const graphics = new Graphics();

    for (let index = 0; index < count; index += 1) {
        const startAngle = index * angularPeriod;
        const endAngle = startAngle + angularPeriod * dashFraction;
        const subdivisions = 3;

        for (let step = 0; step < subdivisions; step += 1) {
            const leftAngle = startAngle
                + (endAngle - startAngle) * (step / subdivisions);
            const rightAngle = startAngle
                + (endAngle - startAngle) * ((step + 1) / subdivisions);
            const leftX = center.x + Math.cos(leftAngle) * radius;
            const leftY = center.y + Math.sin(leftAngle) * radius;
            const rightX = center.x + Math.cos(rightAngle) * radius;
            const rightY = center.y + Math.sin(rightAngle) * radius;
            graphics
                .moveTo(leftX, leftY)
                .lineTo(rightX, rightY);
        }
    }

    graphics.stroke({ color, alpha: 0.66, width: 1.15 });
    world.addChild(graphics);

    const fill = new Graphics()
        .circle(center.x, center.y, radius)
        .fill({ color, alpha: 0.018 });
    world.addChildAt(fill, 0);
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
    const sightingDistance = routeDistance([origin, sighting]);

    const from = rendered(origin, bounds);
    const target = rendered(sighting, bounds);
    const rangeColor = 0xffc266;
    const sightingColor = 0xf29bff;

    drawSightingMarker(world, target, sightingColor);
    drawDashedCircle(
        world,
        from,
        Math.max(item.max_distance, 0),
        rangeColor,
    );

    if (item.max_distance >= 0.5) {
        const rangeLabel = new Text({
            text: (
                `INTERCEPT RANGE ENVELOPE · ≤${item.max_distance.toFixed(1)} ly`
                + ` · W${item.warp ?? "—"} · direction unknown`
            ),
            style: {
                fill: rangeColor,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 9,
                fontWeight: "700",
                stroke: { color: 0x060a10, width: 3 },
            },
            resolution: 2,
        });
        rangeLabel.anchor.set(0.5, 1);
        rangeLabel.position.set(
            from.x,
            from.y - item.max_distance - 5,
        );
        world.addChild(rangeLabel);
    }

    const sightingLabel = new Text({
        text: (
            `TARGET SIGHTING · #${item.target_ship_id ?? "?"}`
            + ` · ${sightingDistance.toFixed(1)} ly`
        ),
        style: {
            fill: sightingColor,
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
