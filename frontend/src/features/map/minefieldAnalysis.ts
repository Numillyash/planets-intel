import type { MapPlanetObservation, MapStellarCartographyObservation, PrivateIntelMapResponse } from "../../types/intel";
import { factNumber, factString, planetFacts } from "./observationView";

export function minefieldOwnerId(
    feature: MapStellarCartographyObservation,
): number | null {
    return factNumber(feature.payload, "ownerid", "owner_id", "owner");
}

export function minefieldFriendlyCode(
    feature: MapStellarCartographyObservation,
): string | null {
    return factString(feature.payload, "friendlycode", "friendly_code", "fcode");
}

export function minefieldIsWeb(
    feature: MapStellarCartographyObservation,
): boolean {
    const value = feature.payload.isweb ?? feature.payload.web ?? feature.payload.is_web;
    return value === true || value === 1 || value === "true" || value === "True";
}

export interface MinefieldPlanetTarget {
    planet: MapPlanetObservation;
    distance: number;
}

export function minefieldSourcePlanet(
    intel: PrivateIntelMapResponse,
    feature: MapStellarCartographyObservation,
): MinefieldPlanetTarget | null {
    if (feature.x === null || feature.y === null) return null;
    const ownerId = minefieldOwnerId(feature);
    if (ownerId === null) return null;

    let best: MinefieldPlanetTarget | null = null;
    for (const planet of intel.planets) {
        if (
            planet.owner_id !== ownerId ||
            planet.x === null ||
            planet.y === null
        ) {
            continue;
        }
        const distance = Math.hypot(
            planet.x - feature.x,
            planet.y - feature.y,
        );
        if (
            best === null ||
            distance < best.distance ||
            (distance === best.distance && planet.planet_id < best.planet.planet_id)
        ) {
            best = { planet, distance };
        }
    }
    return best;
}

export function universalMinefieldCodePlanet(
    intel: PrivateIntelMapResponse,
    feature: MapStellarCartographyObservation,
): MapPlanetObservation | null {
    const ownerId = minefieldOwnerId(feature);
    if (ownerId === null) return null;

    const candidates = intel.planets.filter((planet) => {
        if (planet.owner_id !== ownerId) return false;
        const code = planetFacts(planet).friendlyCode;
        return code !== null && /^mf.$/i.test(code);
    });

    if (candidates.length === 0) return null;
    return candidates.reduce((best, planet) =>
        planet.planet_id > best.planet_id ? planet : best
    );
}
