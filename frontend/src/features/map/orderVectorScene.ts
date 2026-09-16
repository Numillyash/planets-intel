import { Container, Graphics, Text } from "pixi.js";

import type { ShipOrderDraft } from "../../types/orderDraft";
import type {
    DraftMovementPredictionResponse,
    ShipMovementPrediction,
} from "../../types/movementPrediction";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    isCombinedPrivateIntel,
} from "../../types/intel";
import {
    renderY,
    type MapBounds,
    type SelectedEntity,
} from "./mapModel";
import { drawProvisionalInterceptPrediction } from "./interceptProvisionalScene";
import { getCachedMovementPrediction } from "./movementPredictionState";
import {
    routeDistance,
    shipPlannedRoute,
    type MapPoint,
} from "./navigationAnalysis";
import { drawWarpWellPrediction } from "./warpWellPredictionScene";


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


function predictionColor(item: ShipMovementPrediction): number {
    if (item.phase === "intercept") return 0xffa7ff;
    if (item.phase === "tow") return 0xffcf6b;
    return 0x76f0c0;
}


function predictionPhaseLabel(item: ShipMovementPrediction): string {
    if (item.phase === "intercept") return "PREDICTED INTERCEPT";
    if (item.phase === "tow") {
        return item.tow_role === "target"
            ? "PREDICTED TOWED"
            : "PREDICTED TOW";
    }
    return "PREDICTED MOVE";
}


function hasRenderablePrediction(item: ShipMovementPrediction | undefined): boolean {
    return item !== undefined
        && item.start_x !== null
        && item.start_y !== null
        && item.predicted_x !== null
        && item.predicted_y !== null;
}


function predictionLabelOffsetY(item: ShipMovementPrediction): number {
    if (item.phase !== "tow") return 0;
    return item.tow_role === "target" ? 10 : -10;
}


function isUnresolvedTowLock(
    item: ShipMovementPrediction | undefined,
): item is ShipMovementPrediction {
    return item !== undefined
        && item.phase === "tow"
        && item.tow_lock_status === "unknown"
        && item.start_x !== null
        && item.start_y !== null
        && item.predicted_x === null
        && item.predicted_y === null
        && item.pre_well_x === null
        && item.pre_well_y === null;
}


function drawUnresolvedTowLock(
    world: Container,
    bounds: MapBounds,
    item: ShipMovementPrediction,
): boolean {
    if (!isUnresolvedTowLock(item)) {
        return false;
    }

    // Keep unresolved Tow visible without turning the map into a diagnostic
    // console. The tower gets a small amber halo; the actual planned vector is
    // recolored below when it comes from a local draft. The paired target row
    // intentionally adds no duplicate marker or text at the same coordinates.
    if (item.tow_role === "target") {
        return true;
    }

    const point = rendered({
        x: item.start_x as number,
        y: item.start_y as number,
    }, bounds);
    const color = predictionColor(item);
    const marker = new Graphics()
        .circle(point.x, point.y, 7)
        .stroke({ color, alpha: 0.78, width: 1.25 });
    world.addChild(marker);

    return true;
}


function drawPrediction(
    world: Container,
    bounds: MapBounds,
    item: ShipMovementPrediction,
    labelOffsetY = 0,
) {
    if (drawWarpWellPrediction({ world, bounds, item })) {
        return;
    }

    if (drawUnresolvedTowLock(world, bounds, item)) {
        return;
    }

    if (!hasRenderablePrediction(item)) {
        return;
    }

    const route: MapPoint[] = [
        { x: item.start_x as number, y: item.start_y as number },
        { x: item.predicted_x as number, y: item.predicted_y as number },
    ];
    const distance = routeDistance(route);
    if (distance < 0.5) return;

    const from = rendered(route[0], bounds);
    const to = rendered(route[1], bounds);
    const color = predictionColor(item);
    const alpha = item.certain ? 0.88 : 0.52;

    const path = new Graphics()
        .moveTo(from.x, from.y)
        .lineTo(to.x, to.y)
        .stroke({ color, alpha, width: 1.65 });
    world.addChild(path);
    drawArrowHead(world, from, to, color, alpha, 1.65, 6.5);

    const endpoint = new Graphics()
        .circle(to.x, to.y, 3.6)
        .fill({ color, alpha: 0.28 })
        .stroke({ color, alpha: 0.96, width: 1.2 });
    world.addChild(endpoint);

    const moved = item.moved_distance ?? distance;
    const phaseLabel = predictionPhaseLabel(item);
    const label = new Text({
        text: `${phaseLabel} · ${moved.toFixed(1)} ly · W${item.warp ?? "—"}`,
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
        (from.y + to.y) / 2 - 5 + labelOffsetY,
    );
    world.addChild(label);
}


export function drawOrderVectors({
    world,
    intel,
    bounds,
    selected,
    drafts,
    prediction: suppliedPrediction,
}: {
    world: Container;
    intel: PrivateIntelMapResponse;
    bounds: MapBounds;
    selected: SelectedEntity | null;
    drafts: ShipOrderDraft[];
    prediction?: DraftMovementPredictionResponse | null;
}) {
    const primarySlotId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
    const linkedAccountId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;
    const prediction = suppliedPrediction ?? getCachedMovementPrediction(
        intel.game_id,
        linkedAccountId,
        intel.turn,
    );
    const selectedShipId = selected?.kind === "ship"
        ? selected.value.ship_id
        : null;
    const draftByShipId = new Map(
        drafts.map((draft) => [draft.ship_id, draft]),
    );
    const predictionByShipId = new Map(
        (prediction?.items ?? []).map((item) => [item.ship_id, item]),
    );
    const shipById = new Map(
        intel.ships.map((ship) => [ship.ship_id, ship]),
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

        const predicted = predictionByShipId.get(ship.ship_id);

        if (
            draft.movement_mode === "intercept"
            && draft.intercept_target_ship_id !== null
        ) {
            const target = shipById.get(draft.intercept_target_ship_id);
            if (
                target !== undefined
                && target.x !== null
                && target.y !== null
            ) {
                const lockRoute: MapPoint[] = [
                    { x: ship.x, y: ship.y },
                    { x: target.x, y: target.y },
                ];
                const lockDistance = routeDistance(lockRoute);
                if (lockDistance >= 0.5) {
                    drawVector({
                        world,
                        route: lockRoute,
                        bounds,
                        color: draft.stale ? 0xffc766 : 0xf29bff,
                        alpha: 0.62,
                        width: 1.35,
                        dashLength: 6,
                        gapLength: 5,
                        label: `LOCK #${target.ship_id} · ${lockDistance.toFixed(0)} ly`,
                    });
                }
            }

            if (predicted !== undefined) {
                drawProvisionalInterceptPrediction({
                    world,
                    bounds,
                    item: predicted,
                });
            }
            continue;
        }

        const targetX = draft.waypoint_x ?? draft.upstream_waypoint_x;
        const targetY = draft.waypoint_y ?? draft.upstream_waypoint_y;
        if (targetX !== null && targetY !== null) {
            const draftRoute: MapPoint[] = [
                { x: ship.x, y: ship.y },
                { x: targetX, y: targetY },
            ];
            const distance = routeDistance(draftRoute);
            if (distance >= 0.5) {
                const unresolvedTowTower = isUnresolvedTowLock(predicted)
                    && predicted.tow_role !== "target";
                const color = draft.stale
                    ? 0xffc766
                    : unresolvedTowTower
                        ? predictionColor(predicted)
                        : 0xa8eaff;
                drawVector({
                    world,
                    route: draftRoute,
                    bounds,
                    color,
                    alpha: 0.72,
                    width: 1.55,
                    dashLength: 10,
                    gapLength: 5,
                    label: hasRenderablePrediction(predicted)
                        ? null
                        : `DRAFT · ${distance.toFixed(1)} ly · W${draft.warp ?? draft.upstream_warp ?? "—"}`,
                });
            }
        }
    }

    // Prediction rows are derived outputs, not merely annotations for ships
    // that happen to have their own local draft. In particular, a Tow target
    // normally has no draft of its own but still receives a `tow_role=target`
    // prediction row. Render the response independently so PREDICTED TOWED is
    // not silently dropped. Offsetting the paired Tow labels also keeps the
    // tower and target text legible when their routes coincide exactly.
    for (const item of prediction?.items ?? []) {
        drawPrediction(
            world,
            bounds,
            item,
            predictionLabelOffsetY(item),
        );
    }
}
