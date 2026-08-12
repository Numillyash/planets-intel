import type {
    PlanetObservationResponse,
    ShipObservationResponse,
} from "../../types/api";
import type {
    MapPlanetObservation,
    MapShipObservation,
    MapStarbaseObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";

export type PlanetLabelMode = "none" | "id" | "name";
export type ShipRole = "freighter" | "torpedo" | "carrier" | "warship";

export type SelectedEntity =
    | { kind: "planet"; value: MapPlanetObservation }
    | { kind: "ship"; value: MapShipObservation }
    | { kind: "starbase"; value: MapStarbaseObservation };

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
export const PLANET_RADIUS = 7;
export const PLANET_ORBIT_RADIUS = 18;

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

export function observedBounds(intel: PrivateIntelMapResponse): MapBounds {
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

export function renderY(y: number, bounds: MapBounds): number {
    return bounds.minY + bounds.maxY - y;
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

export function planetLinks(
    planets: MapPlanetObservation[],
    maxDistance = PLANET_LINK_RANGE,
): PlanetLink[] {
    const positioned = planets.filter(
        (planet): planet is MapPlanetObservation & { x: number; y: number } =>
            planet.x !== null && planet.y !== null,
    );
    const maxDistanceSquared = maxDistance * maxDistance;
    const links: PlanetLink[] = [];

    for (let left = 0; left < positioned.length; left += 1) {
        for (let right = left + 1; right < positioned.length; right += 1) {
            const from = positioned[left];
            const to = positioned[right];
            const dx = from.x - to.x;
            const dy = from.y - to.y;
            if (dx * dx + dy * dy <= maxDistanceSquared) {
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

    const radius = baseRadius + ring * 10;
    const countOnRing = Math.min(capacity, size - (index - remainingIndex));
    const angle = -Math.PI / 2 + (Math.PI * 2 * remainingIndex) / Math.max(countOnRing, 1);

    return {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
    };
}

export function shipVisualPositions(
    intel: PrivateIntelMapResponse,
    bounds: MapBounds,
): ShipVisualPosition[] {
    const planetAt = new Map<string, MapPlanetObservation>();
    for (const planet of intel.planets) {
        if (planet.x !== null && planet.y !== null) {
            planetAt.set(coordinateKey(planet.x, planet.y), planet);
        }
    }

    const groups = new Map<string, MapShipObservation[]>();
    for (const ship of intel.ships) {
        if (ship.x === null || ship.y === null) {
            continue;
        }
        const key = coordinateKey(ship.x, ship.y);
        const group = groups.get(key) ?? [];
        group.push(ship);
        groups.set(key, group);
    }

    const result: ShipVisualPosition[] = [];

    for (const [key, ships] of groups) {
        const first = ships[0];
        if (first.x === null || first.y === null) {
            continue;
        }

        const anchorX = first.x;
        const anchorY = renderY(first.y, bounds);
        const planet = planetAt.get(key) ?? null;

        ships.forEach((ship, index) => {
            let offset = { x: 0, y: 0 };

            if (planet !== null) {
                offset = clusteredOffset(
                    index,
                    ships.length,
                    PLANET_ORBIT_RADIUS,
                    8,
                    true,
                );
            } else if (ships.length > 1) {
                offset = clusteredOffset(index, ships.length, 10, 6);
            }

            result.push({
                ship,
                anchorX,
                anchorY,
                x: anchorX + offset.x,
                y: anchorY + offset.y,
                planetId: planet?.planet_id ?? null,
                clusterSize: ships.length,
                clusterIndex: index,
            });
        });
    }

    return result;
}
