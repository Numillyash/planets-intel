import type { PlanetObservationResponse } from "../../types/api";
import { factNumber } from "./observationView";

/**
 * A Planets.nu planet row is NOT automatically a surveyed planet.
 *
 * A position/owner-only row may carry zero-valued defaults in arbitrary
 * economy, native and climate fields. A positive info_turn is necessary for
 * attributing observation, but even it can mean only "owner last seen".
 *
 * Do not infer a survey from the *presence* of a 0 value (temp:0,
 * clans:0, mines:0, native tax:0 etc). A genuine zero is possible, but
 * source data without a disclosure flag cannot distinguish it from a
 * placeholder. Abstain in that case instead of painting every grey planet.
 */
export function hasPlanetSurveyEvidence(planet: PlanetObservationResponse): boolean {
    if (planet.info_turn === null || planet.info_turn <= 0) return false;

    const payload = planet.payload;
    // Nonzero observed values demonstrate disclosed information beyond a
    // planet's identity/location and owner. Require only one, but NEVER
    // treat nominal zero defaults as evidence of a scan.
    const disclosed = [
        ["temp", "temperature"],
        ["clans", "colonistclans", "colonists"],
        ["nativeclans", "native_clans"],
        ["mines"],
        ["factories"],
        ["defense", "defenseposts", "defense_posts"],
        ["supplies"],
        ["megacredits", "money", "mc"],
        ["neutronium"], ["duranium"], ["tritanium"], ["molybdenum"],
        ["groundneutronium", "neutroniumground", "neutronium_ground"],
        ["groundduranium", "duraniumground", "duranium_ground"],
        ["groundtritanium", "tritaniumground", "tritanium_ground"],
        ["groundmolybdenum", "molybdenumground", "molybdenum_ground"],
        ["densityneutronium", "neutroniumdensity", "neutronium_density"],
        ["densityduranium", "duraniumdensity", "duranium_density"],
        ["densitytritanium", "tritaniumdensity", "tritanium_density"],
        ["densitymolybdenum", "molybdenumdensity", "molybdenum_density"],
    ] as const;
    return disclosed.some((keys) => {
        const field = factNumber(payload, ...keys);
        return field !== null && field > 0;
    });
}

/** Presence of actual details is separate from planet ownership. */
export function showForeignPlanetSurveyRing(
    planet: PlanetObservationResponse,
    observerSlotId: number,
): boolean {
    return planet.owner_id !== observerSlotId && hasPlanetSurveyEvidence(planet);
}
