import type {
    LatestPrivateIntelResponse,
    PlanetObservationResponse,
    ShipObservationResponse,
} from "../../types/api";

export type PlanetLabelMode = "none" | "id" | "name";
export type ShipRole = "freighter" | "torpedo" | "carrier" | "warship";

export interface MapBounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

export interface PlanetLink {
    from: PlanetObservationResponse;
    to: PlanetObservationResponse;
}

export const PLANET_LINK_RANGE = 81;

export const SHIP_ROLE_LABEL: Record<ShipRole, string> = {
    freighter: "Freighter",
    torpedo: "Torpedo ship",
    carrier: "Fighter carrier",
    warship: "Combat ship",
};

const COMMON_DEEP_SPACE_FREIGHTER_HULL_IDS = new Set([15, 16, 17]);

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

export function observedBounds(intel: LatestPrivateIntelResponse): MapBounds {
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
    planets: PlanetObservationResponse[],
    maxDistance = PLANET_LINK_RANGE,
): PlanetLink[] {
    const positioned = planets.filter(
        (planet): planet is PlanetObservationResponse & { x: number; y: number } =>
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
