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


function compactLabel(
    text: string,
    color: number,
    fontSize = 8,
): Text {
    return new Text({
        text,
        style: {
            fill: color,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize,
            fontWeight: "700",
            stroke: { color: 0x060a10, width: 2.5 },
        },
        resolution: 2,
    });
}


function drawSightingMarker(
    world: Container,
    point: RenderPoint,
    color: number,
) {
    const marker = new Graphics()
        .circle(point.x, point.y, 5.5)
        .stroke({ color, alpha: 0.86, width: 1.05 })
        .moveTo(point.x - 7.5, point.y)
        .lineTo(point.x + 7.5, point.y)
        .moveTo(point.x, point.y - 7.5)
        .lineTo(point.x, point.y + 7.5)
        .stroke({ color, alpha: 0.62, width: 0.9 });
    world.addChild(marker);
}


function drawDashedCircle(
    world: Container,
    center: RenderPoint,
    radius: number,
    color: number,
    alpha: number,
    width: number,
    fillAlpha: number,
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
            graphics
                .moveTo(
                    center.x + Math.cos(leftAngle) * radius,
                    center.y + Math.sin(leftAngle) * radius,
                )
                .lineTo(
                    center.x + Math.cos(rightAngle) * radius,
                    center.y + Math.sin(rightAngle) * radius,
                );
        }
    }

    graphics.stroke({ color, alpha, width });
    world.addChild(graphics);

    if (fillAlpha > 0) {
        const fill = new Graphics()
            .circle(center.x, center.y, radius)
            .fill({ color, alpha: fillAlpha });
        world.addChildAt(fill, 0);
    }
}


function drawDirectionSector({
    world,
    origin,
    interceptRange,
    target,
    targetRange,
    color,
}: {
    world: Container;
    origin: RenderPoint;
    interceptRange: number;
    target: RenderPoint;
    targetRange: number;
    color: number;
}) {
    if (interceptRange < 0.5 || targetRange < 0) return;

    const dx = target.x - origin.x;
    const dy = target.y - origin.y;
    const centerDistance = Math.hypot(dx, dy);
    if (centerDistance < 0.001) {
        drawDashedCircle(
            world,
            origin,
            interceptRange,
            color,
            0.9,
            2,
            0.018,
        );
        return;
    }

    const centerAngle = Math.atan2(dy, dx);
    const halfAngle = targetRange >= centerDistance
        ? Math.PI
        : Math.asin(Math.min(Math.max(targetRange / centerDistance, 0), 1));

    if (halfAngle >= Math.PI - 0.001) {
        const ring = new Graphics()
            .circle(origin.x, origin.y, interceptRange)
            .stroke({ color, alpha: 0.88, width: 2.1 });
        world.addChild(ring);
        return;
    }

    const visibleHalfAngle = Math.max(halfAngle, 0.025);
    const startAngle = centerAngle - visibleHalfAngle;
    const endAngle = centerAngle + visibleHalfAngle;
    const steps = Math.max(12, Math.ceil(visibleHalfAngle * 24));
    const sector = new Graphics()
        .moveTo(origin.x, origin.y)
        .lineTo(
            origin.x + Math.cos(startAngle) * interceptRange,
            origin.y + Math.sin(startAngle) * interceptRange,
        );

    for (let step = 1; step <= steps; step += 1) {
        const angle = startAngle
            + (endAngle - startAngle) * (step / steps);
        sector.lineTo(
            origin.x + Math.cos(angle) * interceptRange,
            origin.y + Math.sin(angle) * interceptRange,
        );
    }

    sector
        .lineTo(origin.x, origin.y)
        .fill({ color, alpha: 0.035 });
    world.addChildAt(sector, 0);

    const arc = new Graphics();
    for (let step = 0; step < steps; step += 1) {
        const leftAngle = startAngle
            + (endAngle - startAngle) * (step / steps);
        const rightAngle = startAngle
            + (endAngle - startAngle) * ((step + 1) / steps);
        arc
            .moveTo(
                origin.x + Math.cos(leftAngle) * interceptRange,
                origin.y + Math.sin(leftAngle) * interceptRange,
            )
            .lineTo(
                origin.x + Math.cos(rightAngle) * interceptRange,
                origin.y + Math.sin(rightAngle) * interceptRange,
            );
    }
    arc.stroke({ color, alpha: 0.94, width: 2.15 });
    world.addChild(arc);

    const labelAngle = centerAngle;
    const label = compactLabel("STD DIR", color, 7.5);
    label.anchor.set(0.5, 1);
    label.position.set(
        origin.x + Math.cos(labelAngle) * (interceptRange + 4),
        origin.y + Math.sin(labelAngle) * (interceptRange + 4),
    );
    world.addChild(label);
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
    const targetEnvelopeColor = 0xc987e8;
    const interceptRange = Math.max(item.max_distance, 0);
    const targetRange = item.target_standard_max_distance;

    drawSightingMarker(world, target, sightingColor);
    drawDashedCircle(
        world,
        from,
        interceptRange,
        rangeColor,
        0.48,
        0.95,
        0.012,
    );

    if (interceptRange >= 0.5) {
        const rangeLabel = compactLabel(
            `RANGE ≤${interceptRange.toFixed(0)} · W${item.warp ?? "—"}`,
            rangeColor,
        );
        rangeLabel.anchor.set(0.5, 1);
        rangeLabel.position.set(from.x, from.y - interceptRange - 4);
        world.addChild(rangeLabel);
    }

    if (targetRange !== null) {
        drawDashedCircle(
            world,
            target,
            Math.max(targetRange, 0),
            targetEnvelopeColor,
            0.34,
            0.9,
            0.008,
        );
        drawDirectionSector({
            world,
            origin: from,
            interceptRange,
            target,
            targetRange: Math.max(targetRange, 0),
            color: rangeColor,
        });

        const targetRangeLabel = compactLabel(
            `TARGET STD ≤${targetRange.toFixed(0)} · W${item.target_warp ?? "—"}`,
            targetEnvelopeColor,
            7.5,
        );
        targetRangeLabel.anchor.set(0.5, 1);
        targetRangeLabel.position.set(
            target.x,
            target.y - Math.max(targetRange, 0) - 3,
        );
        world.addChild(targetRangeLabel);
    }

    const sightingLabel = compactLabel(
        `SIGHT #${item.target_ship_id ?? "?"} · ${sightingDistance.toFixed(0)} ly`,
        sightingColor,
    );
    sightingLabel.anchor.set(0.5, 0);
    sightingLabel.position.set(target.x, target.y + 8);
    world.addChild(sightingLabel);
}
