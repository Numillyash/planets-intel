import { Container, Graphics, Text } from "pixi.js";

import type { ShipOrderDraft } from "../../types/orderDraft";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    isCombinedPrivateIntel,
} from "../../types/intel";
import {
    renderY,
    type MapBounds,
    type SelectedEntity,
} from "./mapModel";
import {
    routeDistance,
    shipPlannedRoute,
    type MapPoint,
} from "./navigationAnalysis";


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


function drawDashedSegment(
    graphics: Graphics,
    from: RenderPoint,
    to: RenderPoint,
    dashLength: number,
    gapLength: number,
) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy);
    if (length < 0.001) return;

    const ux = dx / length;
    const uy = dy / length;
    const period = Math.max(dashLength + gapLength, 0.1);

    for (let distance = 0; distance < length; distance += period) {
        const endDistance = Math.min(distance + dashLength, length);
        graphics
            .moveTo(
                from.x + ux * distance,
                from.y + uy * distance,
            )
            .lineTo(
                from.x + ux * endDistance,
                from.y + uy * endDistance,
            );
    }
}


function drawArrowHead(
    world: Container,
    from: RenderPoint,
    to: RenderPoint,
    color: number,
    alpha: number,
    width: number,
    size: number,
) {
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const wing = Math.PI * 0.78;
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
        .stroke({ color, alpha, width });
    world.addChild(arrow);
}


function drawVector({
    world,
    route,
    bounds,
    color,
    alpha,
    width,
    dashLength,
    gapLength,
    label,
}: {
    world: Container;
    route: MapPoint[];
    bounds: MapBounds;
    color: number;
    alpha: number;
    width: number;
    dashLength: number;
    gapLength: number;
    label: string | null;
}) {
    if (route.length < 2 || routeDistance(route) < 0.5) return;

    const path = new Graphics();
    for (let index = 1; index < route.length; index += 1) {
        drawDashedSegment(
            path,
            rendered(route[index - 1], bounds),
            rendered(route[index], bounds),
            dashLength,
            gapLength,
        );
    }
    path.stroke({ color, alpha, width });
    world.addChild(path);

    const previous = rendered(route[route.length - 2], bounds);
    const target = rendered(route[route.length - 1], bounds);
    drawArrowHead(
        world,
        previous,
        target,
        color,
        Math.min(alpha + 0.08, 1),
        width,
        width >= 2 ? 7 : 5.5,
    );

    if (label === null) return;

    const midpoint = {
        x: (previous.x + target.x) / 2,
        y: (previous.y + target.y) / 2,
    };
    const text = new Text({
        text: label,
        style: {
            fill: color,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 9,
            fontWeight: "600",
            stroke: { color: 0x060a10, width: 3 },
        },
        resolution: 2,
    });
    text.anchor.set(0.5, 1);
    text.position.set(midpoint.x, midpoint.y - 4);
    world.addChild(text);
}


export function drawOrderVectors({
    world,
    intel,
    bounds,
    selected,
    drafts,
}: {
    world: Container;
    intel: PrivateIntelMapResponse;
    bounds: MapBounds;
    selected: SelectedEntity | null;
    drafts: ShipOrderDraft[];
}) {
    const primarySlotId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
    const selectedShipId = selected?.kind === "ship"
        ? selected.value.ship_id
        : null;
    const draftByShipId = new Map(
        drafts.map((draft) => [draft.ship_id, draft]),
    );

    for (const ship of intel.ships) {
        if (
            ship.owner_id !== primarySlotId
            || ship.x === null
            || ship.y === null
        ) {
            continue;
        }

        const upstreamRoute = shipPlannedRoute(ship);
        const upstreamDistance = routeDistance(upstreamRoute);
        const selectedShip = selectedShipId === ship.ship_id;

        // mapScene already renders the selected ship's factual trajectory with
        // the stronger selection treatment. The dashed layer is the persistent
        // cue for orders belonging to ships that are not currently selected.
        if (
            !selectedShip
            && upstreamRoute.length >= 2
            && upstreamDistance >= 0.5
        ) {
            drawVector({
                world,
                route: upstreamRoute,
                bounds,
                color: 0x62cfff,
                alpha: 0.36,
                width: 0.95,
                dashLength: 7,
                gapLength: 5,
                label: null,
            });
        }

        const draft = draftByShipId.get(ship.ship_id);
        if (draft === undefined) continue;

        const targetX = draft.waypoint_x ?? draft.upstream_waypoint_x;
        const targetY = draft.waypoint_y ?? draft.upstream_waypoint_y;
        if (targetX === null || targetY === null) continue;

        const draftRoute: MapPoint[] = [
            { x: ship.x, y: ship.y },
            { x: targetX, y: targetY },
        ];
        const distance = routeDistance(draftRoute);
        if (distance < 0.5) continue;

        const color = draft.stale ? 0xffc766 : 0xa8eaff;
        drawVector({
            world,
            route: draftRoute,
            bounds,
            color,
            alpha: 0.96,
            width: 2.15,
            dashLength: 10,
            gapLength: 5,
            label: `DRAFT · ${distance.toFixed(1)} ly · W${draft.warp ?? draft.upstream_warp ?? "—"}`,
        });
    }
}
