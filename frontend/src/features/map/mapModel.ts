import type {
    PlanetObservationResponse,
    ShipObservationResponse,
} from "../../types/api";
import type {
    MapPlanetObservation,
    MapShipObservation,
    MapStarbaseObservation,
    MapStellarCartographyObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";

export type MapObservationSet = Pick<
    import("../../types/api").LatestPrivateIntelResponse,
    "game_id" | "turn" | "planets" | "ships" | "starbases" | "stellar_cartography"
>;

export type PlanetLabelMode = "none" | "id" | "name";
export type ShipRole = "freighter" | "torpedo" | "carrier" | "warship";

type PositionedShip = MapShipObservation & { x: number; y: number };

export type SelectedEntity =
    | { kind: "planet"; value: MapPlanetObservation }
    | { kind: "ship"; value: MapShipObservation }
    | { kind: "starbase"; value: MapStarbaseObservation }
    | { kind: "stellar"; value: MapStellarCartographyObservation };

export interface MapBounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

export interface PlanetLink {
    from: MapPlanetObservation;
    to: MapPlanetObservation;
}

export interface ShipVisualPosition {
    ship: MapShipObservation;
    anchorX: number;
    anchorY: number;
    x: number;
    y: number;
    planetId: number | null;
    clusterSize: number;
    clusterIndex: number;
}

export const PLANET_LINK_RANGE = 81;
export const PLANET_WARP_WELL_RADIUS = 3;
export const PLANET_RADIUS = 7;
// Visual separation only. Keep it compact enough that a ship still reads as
// being at the planet rather than physically many light-years away.
export const PLANET_ORBIT_RADIUS = 10;

export const SHIP_ROLE_LABEL: Record<ShipRole, string> = {
    freighter: "Freighter",
    torpedo: "Torpedo ship",
    carrier: "Fighter carrier",
    warship: "Combat ship",
};

const COMMON_DEEP_SPACE_FREIGHTER_HULL_IDS = new Set([15, 16, 17]);

function coordinateKey(x: number, y: number): string {
    return `${x}:${y}`;
}

function payloadNumber(
    ship: ShipObservationResponse,
    ...keys: string[]
): number | null {
    for (const key of keys) {
        const value = ship.payload[key];
        if (typeof value === "number" && Number.isFinite(value)) {
            return value;
        }
    }
    return null;
}

function payloadString(
    ship: ShipObservationResponse,
    ...keys: string[]
): string | null {
    for (const key of keys) {
        const value = ship.payload[key];
        if (typeof value === "string" && value.trim()) {
            return value.trim();
        }
    }
    return null;
}

export function shipRole(ship: ShipObservationResponse): ShipRole {
    const bays = payloadNumber(ship, "bays", "fighterbays", "baycount") ?? 0;
    if (bays > 0) {
        return "carrier";
    }

    const tubes = payloadNumber(ship, "tubes", "torpedotubes", "tubecount") ?? 0;
    if (tubes > 0) {
        return "torpedo";
    }

    const hullName = payloadString(ship, "hullname", "hullName") ?? "";
    const descriptiveName = `${hullName} ${ship.name ?? ""}`.toLowerCase();
    if (
        descriptiveName.includes("freighter") ||
        (ship.hull_id !== null && COMMON_DEEP_SPACE_FREIGHTER_HULL_IDS.has(ship.hull_id))
    ) {
        return "freighter";
    }

    return "warship";
}

export function observedBounds(intel: MapObservationSet): MapBounds {
    const coordinates: Array<{ x: number; y: number }> = [];

    for (const planet of intel.planets) {
        if (planet.x !== null && planet.y !== null) {
            coordinates.push({ x: planet.x, y: planet.y });
        }
    }

    for (const ship of intel.ships) {
        if (ship.x !== null && ship.y !== null) {
            coordinates.push({ x: ship.x, y: ship.y });
        }
    }

    for (const feature of intel.stellar_cartography) {
        if (feature.x === null || feature.y === null) {
            continue;
        }

        const radius = Math.max(feature.radius ?? 0, 0);
        coordinates.push(
            { x: feature.x - radius, y: feature.y - radius },
            { x: feature.x + radius, y: feature.y + radius },
        );

        if (feature.feature_type === "star_cluster") {
            const mass = feature.payload.mass;
            if (typeof mass === "number" && Number.isFinite(mass) && mass > 0) {
                const haloRadius = Math.sqrt(mass);
                coordinates.push(
                    { x: feature.x - haloRadius, y: feature.y - haloRadius },
                    { x: feature.x + haloRadius, y: feature.y + haloRadius },
                );
            }
        }
    }

    if (coordinates.length === 0) {
        return { minX: 0, maxX: 100, minY: 0, maxY: 100 };
    }

    const xs = coordinates.map((point) => point.x);
    const ys = coordinates.map((point) => point.y);
    const rawMinX = Math.min(...xs);
    const rawMaxX = Math.max(...xs);
    const rawMinY = Math.min(...ys);
    const rawMaxY = Math.max(...ys);
    const width = Math.max(rawMaxX - rawMinX, 1);
    const height = Math.max(rawMaxY - rawMinY, 1);
    const padX = Math.max(width * 0.08, 35);
    const padY = Math.max(height * 0.08, 35);

    return {
        minX: rawMinX - padX,
        maxX: rawMaxX + padX,
        minY: rawMinY - padY,
        maxY: rawMaxY + padY,
    };
}

export function renderY(y: number, _bounds: MapBounds): number {
    // Keep the factual-to-render transform independent from whichever entities
    // happen to be visible in one snapshot. The previous minY+maxY-y transform
    // changed its translation as snapshot bounds changed, making the whole map
    // appear to move when stepping through historical turns.
    return -y;
}

export function planetLabel(
    planet: PlanetObservationResponse,
    mode: PlanetLabelMode,
): string | null {
    if (mode === "none") {
        return null;
    }
    if (mode === "id") {
        return String(planet.planet_id);
    }
    return planet.name ?? `#${planet.planet_id}`;
}

export function planetLinkNavigationDistance(
    from: { x: number; y: number },
    to: { x: number; y: number },
    warpWellRadius = PLANET_WARP_WELL_RADIUS,
): number {
    // The stock starmap link means that a normal W9 ship can reach some
    // integer coordinate inside the target planet's warp-well grid and then be
    // snapped into orbit. Do not simply subtract 3 from the continuous
    // center-to-center distance: the actual destination is an integer map
    // square and edge cases differ by one light-year after navigation rounding.
    //
    // Tesmond (2187,2238) -> Saratoga (2210,2157): center distance 84.20 ly.
    // The warp-well square at (2210,2160), exactly 3 ly from Saratoga, is
    // 81.32 ly from Tesmond and therefore has navigation distance round(...)=81.
    const coordinateRadius = Math.ceil(Math.max(0, warpWellRadius));
    let best = Math.round(Math.hypot(from.x - to.x, from.y - to.y));

    for (let offsetX = -coordinateRadius; offsetX <= coordinateRadius; offsetX += 1) {
        for (let offsetY = -coordinateRadius; offsetY <= coordinateRadius; offsetY += 1) {
            if (Math.hypot(offsetX, offsetY) > warpWellRadius + 1e-9) {
                continue;
            }
            const distance = Math.round(Math.hypot(
                from.x - (to.x + offsetX),
                from.y - (to.y + offsetY),
            ));
            best = Math.min(best, distance);
        }
    }

    return best;
}

export function planetLinks(
    planets: MapPlanetObservation[],
    maxDistance = PLANET_LINK_RANGE,
): PlanetLink[] {
    const positioned = planets.filter(
        (planet): planet is MapPlanetObservation & { x: number; y: number } =>
            planet.x !== null && planet.y !== null,
    );
    const links: PlanetLink[] = [];

    for (let left = 0; left < positioned.length; left += 1) {
        for (let right = left + 1; right < positioned.length; right += 1) {
            const from = positioned[left];
            const to = positioned[right];
            const navigationDistance = planetLinkNavigationDistance(from, to);
            if (navigationDistance <= maxDistance) {
                links.push({ from, to });
            }
        }
    }

    return links;
}

export function starbaseByPlanetId(
    starbases: MapStarbaseObservation[],
): Map<number, MapStarbaseObservation> {
    const result = new Map<number, MapStarbaseObservation>();
    for (const starbase of starbases) {
        if (starbase.planet_id !== null) {
            result.set(starbase.planet_id, starbase);
        }
    }
    return result;
}

export function shipsAtPlanet(
    ships: MapShipObservation[],
    planet: PlanetObservationResponse,
): MapShipObservation[] {
    if (planet.x === null || planet.y === null) {
        return [];
    }
    return ships.filter(
        (ship) => ship.x === planet.x && ship.y === planet.y,
    );
}

function clusteredOffset(
    index: number,
    size: number,
    baseRadius: number,
    firstRingCapacity: number,
    alwaysOffset = false,
): { x: number; y: number } {
    if (size <= 1 && !alwaysOffset) {
        return { x: 0, y: 0 };
    }

    let remainingIndex = index;
    let ring = 0;
    let capacity = firstRingCapacity;

    while (remainingIndex >= capacity) {
        remainingIndex -= capacity;
        ring += 1;
        capacity = firstRingCapacity + ring * 4;
    }

    const radius = baseRadius + ring * Math.max(baseRadius * 0.85, 6);
    const angle = -Math.PI / 2 + (Math.PI * 2 * remainingIndex) / capacity;
    return {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
    };
}

export function shipVisualPositions(
    intel: MapObservationSet,
    bounds: MapBounds,
): ShipVisualPosition[] {
    // PrivateIntelMapResponse is a union whose `ships` member is either the
    // raw observation array or the combined-intel array. TypeScript does not
    // preserve a filter type predicate reliably across that union. Materialize
    // concrete numeric coordinates here instead of relying on downstream
    // control-flow narrowing.
    const positionedShips: PositionedShip[] = [];
    for (const ship of intel.ships) {
        const x = ship.x;
        const y = ship.y;
        if (x === null || y === null) {
            continue;
        }
        positionedShips.push({ ...ship, x, y });
    }

    const planetsByCoordinate = new Map<string, MapPlanetObservation>();
    for (const planet of intel.planets) {
        if (planet.x !== null && planet.y !== null) {
            planetsByCoordinate.set(coordinateKey(planet.x, planet.y), planet);
        }
    }

    const groups = new Map<string, PositionedShip[]>();
    for (const ship of positionedShips) {
        const key = coordinateKey(ship.x, ship.y);
        const group = groups.get(key) ?? [];
        group.push(ship);
        groups.set(key, group);
    }

    const result: ShipVisualPosition[] = [];
    for (const group of groups.values()) {
        group.sort((a, b) => a.ship_id - b.ship_id);
        const first = group[0];
        if (first === undefined) {
            continue;
        }
        const planet = planetsByCoordinate.get(
            coordinateKey(first.x, first.y),
        ) ?? null;

        for (const [index, ship] of group.entries()) {
            const offset = clusteredOffset(
                index,
                group.length,
                PLANET_ORBIT_RADIUS,
                6,
                planet !== null,
            );
            result.push({
                ship,
                anchorX: ship.x,
                anchorY: renderY(ship.y, bounds),
                x: ship.x + offset.x,
                y: renderY(ship.y, bounds) + offset.y,
                planetId: planet?.planet_id ?? null,
                clusterSize: group.length,
                clusterIndex: index,
            });
        }
    }

    return result;
}
