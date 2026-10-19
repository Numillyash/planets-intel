import type { PlanetObservationResponse } from "../../types/api";
import { planetFacts } from "./observationView";

/**
 * Visible planet details independent of owner/position identity.
 *
 * A Planets.nu RST can provide name, x/y, ownerid, infoturn and default
 * nativetaxrate=0 for a position-only or owner-only planet. None of those
 * alone establishes that a planet was surveyed. In particular, the broad
 * knownFieldCount includes some zero placeholders; do not use it here.
 *
 * Read factual fields only; do not substitute inferred intel, stale data
 * from a different slot, or a private observer for public archive views.
 */
export function hasPlanetSurveyEvidence(planet: PlanetObservationResponse): boolean {
    const facts = planetFacts(planet);
    const directValues = [
        facts.temperature,
        facts.clans,
        facts.mines,
        facts.factories,
        facts.defense,
        facts.supplies,
        facts.megacredits,
        facts.nativeClans,
        facts.colonistHappiness,
        facts.colonistTaxRate,
        facts.nativeHappiness,
        facts.friendlyCode,
    ];
    if (directValues.some((value) => value !== null)) return true;

    const mineralDetails = [
        facts.neutronium, facts.duranium, facts.tritanium, facts.molybdenum,
    ];
    if (mineralDetails.some((mineral) =>
        Object.values(mineral).some((value) => value !== null)
    )) return true;

    // A literal "none" or government/race index zero may be sent as a
    // placeholder even with no observed planet details.
    return [facts.nativeRace, facts.nativeGovernment].some(
        (value) => value !== null
            && !/^(none|unknown|race #0|government #0|0|\?+)$/.test(value.toLowerCase()),
    );
}

/** Cyan marker means surveyed *and not owned by the viewing slot*.
 * An enemy owner alone (or just an old infoturn) is not a survey.
 */
export function showForeignPlanetSurveyRing(
    planet: PlanetObservationResponse,
    observerSlotId: number,
): boolean {
    return planet.owner_id !== observerSlotId && hasPlanetSurveyEvidence(planet);
}
