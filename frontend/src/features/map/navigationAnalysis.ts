import type { PlayerInfo } from "../../types/api";
import type {
    MapShipObservation,
    MapStellarCartographyObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";


export interface MapPoint {
    x: number;
    y: number;
}


export interface RadiationSample {
    cluster: MapStellarCartographyObservation;
    distance: number;
    haloRadius: number | null;
    radiation: number;
    insideCore: boolean;
}


export interface RouteRadiationAnalysis {
    maxRadiation: number;
    coreCrossing: boolean;
    cluster: MapStellarCartographyObservation | null;
    closestPoint: MapPoint | null;
    distanceToCenter: number | null;
    haloRadius: number | null;
}


export interface IonStormHazard {
    storm: MapStellarCartographyObservation;
    localVoltage: number;
    stormClass: 1 | 2 | 3 | 4 | 5;
    heading: number | null;
    warp: number | null;
    dragDistance: number | null;
    randomTransportRisk: boolean;
    extremeTransportRisk: boolean;
    cloudy: boolean;
}


function finiteNumber(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : null;
}


function payloadNumber(
    feature: { payload: Record<string, unknown> },
    key: string,
): number | null {
    return finiteNumber(feature.payload[key]);
}


function pointFromUnknown(value: unknown): MapPoint | null {
    if (Array.isArray(value) && value.length >= 2) {
        const x = finiteNumber(value[0]);
        const y = finiteNumber(value[1]);
        return x !== null && y !== null ? { x, y } : null;
    }

    if (value === null || typeof value !== "object") {
        return null;
    }

    const record = value as Record<string, unknown>;
    const x = finiteNumber(record.x ?? record.X);
    const y = finiteNumber(record.y ?? record.Y);
    return x !== null && y !== null ? { x, y } : null;
}


function coordinateList(value: unknown): MapPoint[] {
    if (Array.isArray(value)) {
        return value
            .map((item) => pointFromUnknown(item))
            .filter((item): item is MapPoint => item !== null);
    }

    if (value !== null && typeof value === "object") {
        const direct = pointFromUnknown(value);
        if (direct !== null) {
            return [direct];
        }

        return Object.values(value as Record<string, unknown>)
            .map((item) => pointFromUnknown(item))
            .filter((item): item is MapPoint => item !== null);
    }

    return [];
}


function samePoint(left: MapPoint, right: MapPoint): boolean {
    return left.x === right.x && left.y === right.y;
}


function appendUnique(points: MapPoint[], point: MapPoint | null) {
    if (point === null) {
        return;
    }

    const previous = points[points.length - 1];
    if (previous === undefined || !samePoint(previous, point)) {
        points.push(point);
    }
}


export function shipPlannedRoute(ship: MapShipObservation): MapPoint[] {
    const route: MapPoint[] = [];

    if (ship.x !== null && ship.y !== null) {
        route.push({ x: ship.x, y: ship.y });
    }

    for (const point of coordinateList(ship.payload.waypoints)) {
        appendUnique(route, point);
    }

    const targetX = finiteNumber(
        ship.payload.targetx ?? ship.payload.waypointx,
    );
    const targetY = finiteNumber(
        ship.payload.targety ?? ship.payload.waypointy,
    );
    appendUnique(
        route,
        targetX !== null && targetY !== null
            ? { x: targetX, y: targetY }
            : null,
    );

    return route;
}


export function shipHistoryRoute(ship: MapShipObservation): MapPoint[] {
    const route = coordinateList(ship.payload.history);

    if (ship.x !== null && ship.y !== null) {
        appendUnique(route, { x: ship.x, y: ship.y });
    }

    return route;
}


export function routeDistance(route: MapPoint[]): number {
    let total = 0;

    for (let index = 1; index < route.length; index += 1) {
        total += Math.hypot(
            route[index].x - route[index - 1].x,
            route[index].y - route[index - 1].y,
        );
    }

    return total;
}


function starClusterMetrics(feature: MapStellarCartographyObservation) {
    const mass = payloadNumber(feature, "mass");
    const temperature = payloadNumber(feature, "temp");

    return {
        coreRadius: Math.max(feature.radius ?? 0, 0),
        haloRadius: mass !== null && mass > 0 ? Math.sqrt(mass) : null,
        maxRadiation: temperature !== null
            ? Math.max(temperature / 100, 0)
            : null,
    };
}


function radiationForDistance(
    feature: MapStellarCartographyObservation,
    distance: number,
): RadiationSample | null {
    const metrics = starClusterMetrics(feature);
    const insideCore = metrics.coreRadius > 0 && distance <= metrics.coreRadius;

    if (insideCore) {
        return {
            cluster: feature,
            distance,
            haloRadius: metrics.haloRadius,
            radiation: metrics.maxRadiation !== null
                ? Math.ceil(metrics.maxRadiation)
                : 0,
            insideCore: true,
        };
    }

    if (
        metrics.haloRadius === null ||
        metrics.haloRadius <= 0 ||
        distance > metrics.haloRadius ||
        metrics.maxRadiation === null
    ) {
        return null;
    }

    const radiation = Math.max(
        0,
        Math.ceil(
            metrics.maxRadiation
            * (1 - distance / metrics.haloRadius),
        ),
    );

    return radiation > 0
        ? {
            cluster: feature,
            distance,
            haloRadius: metrics.haloRadius,
            radiation,
            insideCore: false,
        }
        : null;
}


export function radiationAtPoint(
    intel: PrivateIntelMapResponse,
    x: number,
    y: number,
): RadiationSample | null {
    let strongest: RadiationSample | null = null;

    for (const feature of intel.stellar_cartography) {
        if (
            feature.feature_type !== "star_cluster" ||
            feature.x === null ||
            feature.y === null
        ) {
            continue;
        }

        const sample = radiationForDistance(
            feature,
            Math.hypot(x - feature.x, y - feature.y),
        );

        if (sample === null) {
            continue;
        }

        if (
            strongest === null ||
            (sample.insideCore && !strongest.insideCore) ||
            sample.radiation > strongest.radiation
        ) {
            strongest = sample;
        }
    }

    return strongest;
}


function closestPointOnSegment(
    point: MapPoint,
    start: MapPoint,
    end: MapPoint,
): { point: MapPoint; distance: number } {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const lengthSquared = dx * dx + dy * dy;

    if (lengthSquared === 0) {
        return {
            point: start,
            distance: Math.hypot(point.x - start.x, point.y - start.y),
        };
    }

    const projection = (
        (point.x - start.x) * dx +
        (point.y - start.y) * dy
    ) / lengthSquared;
    const t = Math.min(Math.max(projection, 0), 1);
    const closest = {
        x: start.x + dx * t,
        y: start.y + dy * t,
    };

    return {
        point: closest,
        distance: Math.hypot(point.x - closest.x, point.y - closest.y),
    };
}


export function analyzeRouteRadiation(
    intel: PrivateIntelMapResponse,
    route: MapPoint[],
): RouteRadiationAnalysis {
    let best: RouteRadiationAnalysis = {
        maxRadiation: 0,
        coreCrossing: false,
        cluster: null,
        closestPoint: null,
        distanceToCenter: null,
        haloRadius: null,
    };

    if (route.length === 0) {
        return best;
    }

    const segments = route.length === 1
        ? [[route[0], route[0]] as const]
        : route.slice(1).map(
            (point, index) => [route[index], point] as const,
        );

    for (const feature of intel.stellar_cartography) {
        if (
            feature.feature_type !== "star_cluster" ||
            feature.x === null ||
            feature.y === null
        ) {
            continue;
        }

        const center = { x: feature.x, y: feature.y };

        for (const [start, end] of segments) {
            const nearest = closestPointOnSegment(center, start, end);
            const sample = radiationForDistance(feature, nearest.distance);

            if (sample === null) {
                continue;
            }

            if (
                sample.insideCore ||
                (!best.coreCrossing && sample.radiation > best.maxRadiation)
            ) {
                best = {
                    maxRadiation: sample.radiation,
                    coreCrossing: sample.insideCore,
                    cluster: feature,
                    closestPoint: nearest.point,
                    distanceToCenter: nearest.distance,
                    haloRadius: sample.haloRadius,
                };
            }

            if (best.coreCrossing) {
                return best;
            }
        }
    }

    return best;
}


function ionStormClass(voltage: number): 1 | 2 | 3 | 4 | 5 {
    if (voltage < 50) return 1;
    if (voltage < 100) return 2;
    if (voltage < 150) return 3;
    if (voltage < 200) return 4;
    return 5;
}


function ionStormRootId(feature: MapStellarCartographyObservation): number {
    const parentId = payloadNumber(feature, "parentid");
    return parentId !== null && parentId > 0
        ? parentId
        : feature.feature_id;
}


export function ionStormAtPoint(
    intel: PrivateIntelMapResponse,
    x: number,
    y: number,
): IonStormHazard | null {
    const storms = intel.stellar_cartography.filter(
        (feature) => feature.feature_type === "ion_storm",
    );
    const grouped = new Map<number, MapStellarCartographyObservation[]>();

    for (const feature of storms) {
        const rootId = ionStormRootId(feature);
        const group = grouped.get(rootId) ?? [];
        group.push(feature);
        grouped.set(rootId, group);
    }

    let strongest: IonStormHazard | null = null;

    for (const [rootId, group] of grouped) {
        const root = group.find((item) => item.feature_id === rootId) ?? group[0];
        const cloudy = group.length > 1 || group.some(
            (item) => {
                const parentId = payloadNumber(item, "parentid");
                return parentId !== null && parentId > 0;
            },
        );
        let localVoltage = 0;
        let containsPoint = false;

        for (const circle of group) {
            if (
                circle.x === null ||
                circle.y === null ||
                circle.radius === null ||
                circle.radius <= 0
            ) {
                continue;
            }

            const distance = Math.hypot(x - circle.x, y - circle.y);
            if (distance > circle.radius) {
                continue;
            }

            containsPoint = true;
            const centerVoltage = payloadNumber(circle, "voltage") ?? 0;
            localVoltage += cloudy
                ? centerVoltage * Math.max(0, 1 - distance / circle.radius)
                : centerVoltage;
        }

        if (!containsPoint || localVoltage <= 0) {
            continue;
        }

        const warp = payloadNumber(root, "warp");
        const heading = payloadNumber(root, "heading");
        const stormClass = ionStormClass(localVoltage);
        const hazard: IonStormHazard = {
            storm: root,
            localVoltage,
            stormClass,
            heading,
            warp,
            dragDistance:
                stormClass >= 4 && warp !== null && warp > 0
                    ? 0.75 * warp * warp
                    : null,
            randomTransportRisk: localVoltage > 400,
            extremeTransportRisk: localVoltage > 451,
            cloudy,
        };

        if (strongest === null || hazard.localVoltage > strongest.localVoltage) {
            strongest = hazard;
        }
    }

    return strongest;
}


export function shipOwnerRaceId(
    ship: MapShipObservation,
    players: PlayerInfo[],
): number | null {
    if (ship.owner_id === null) {
        return null;
    }

    return players.find(
        (player) => player.slot_id === ship.owner_id,
    )?.race_id ?? null;
}
