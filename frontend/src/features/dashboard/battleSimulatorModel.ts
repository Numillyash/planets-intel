import type { BattleSimulatorCombatant } from "../../api/battleSimulator";
import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";
import type {
    GameDetailsResponse,
    PlanetObservationResponse,
    ShipObservationResponse,
    StarbaseObservationResponse,
} from "../../types/api";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    factNumber,
    planetFacts,
    shipFacts,
    starbaseFacts,
} from "../map/observationView";

export type CandidateKey = `ship:${number}` | `planet:${number}` | `hull:${number}`;
export type SideName = "left" | "right";

export interface ShipSetup {
    kind: "ship";
    baseMass: number;
    physicalBeams: number;
    physicalLaunchers: number;
    physicalBays: number;
}

export interface PlanetSetup {
    kind: "planet";
    planetDefense: number;
    starbasePresent: boolean;
    starbaseDefense: number;
    starbaseBeamTech: number;
    starbaseFighters: number;
}

export interface MaterializedCombatant {
    combatant: BattleSimulatorCombatant;
    warnings: string[];
    setup: ShipSetup | PlanetSetup;
}

export function intValue(record: Record<string, unknown>, ...keys: string[]): number | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "number" && Number.isInteger(value)) return value;
        if (typeof value === "string" && /^-?\d+$/.test(value.trim())) return Number(value);
    }
    return null;
}

export function textValue(record: Record<string, unknown>, ...keys: string[]): string | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "string" && value.trim()) return value.trim();
    }
    return null;
}

export function hullRecord(
    catalog: GameRuleCatalogResponse,
    hullId: number | null,
): Record<string, unknown> | null {
    if (hullId === null) return null;
    return catalog.hulls.find((record) => intValue(record, "id") === hullId) ?? null;
}

function componentIdByName(
    records: Array<Record<string, unknown>>,
    name: string | null,
): number | null {
    if (name === null) return null;
    const folded = name.toLocaleLowerCase();
    const record = records.find(
        (item) => textValue(item, "name")?.toLocaleLowerCase() === folded,
    );
    return record === undefined ? null : intValue(record, "id");
}

function playerRaceId(game: GameDetailsResponse, ownerId: number | null): number | null {
    if (ownerId === null) return null;
    return game.players.find((player) => player.slot_id === ownerId)?.race_id ?? null;
}

export function observerRaceId(
    game: GameDetailsResponse,
    intel: PrivateIntelMapResponse,
): number | null {
    const slot = "primary_observer" in intel
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
    return game.players.find((player) => player.slot_id === slot)?.race_id ?? null;
}

export function raceLabel(
    catalog: GameRuleCatalogResponse,
    raceId: number | null,
): string {
    if (raceId === null) return "No racial bonus";
    const race = catalog.races.find((record) => intValue(record, "id") === raceId);
    return race === undefined
        ? `Race #${raceId}`
        : textValue(race, "name", "shortname") ?? `Race #${raceId}`;
}

function functionalWeaponLimit(
    raceId: number | null,
    damage: number,
    federationCrewBonus: boolean,
): number {
    if (federationCrewBonus) return 10;
    const decade = Math.floor(Math.max(0, damage) / 10);
    if (raceId === 2) return Math.max(0, Math.min(10, 15 - decade));
    return Math.max(0, Math.min(10, 10 - decade));
}

export function normalizeShipForRace(
    value: MaterializedCombatant,
    raceId: number | null,
): MaterializedCombatant {
    if (value.setup.kind !== "ship") return value;
    const fed = raceId === 1;
    const limit = functionalWeaponLimit(raceId, value.combatant.damage, fed);
    const setup = value.setup;
    return {
        ...value,
        combatant: {
            ...value.combatant,
            race_id: raceId,
            federation_crew_bonus: fed,
            mass: Math.max(1, setup.baseMass + (fed ? 50 : 0)),
            physical_beam_count: setup.physicalBeams,
            physical_launcher_count: setup.physicalLaunchers,
            physical_bay_count: setup.physicalBays,
            beam_count: fed ? setup.physicalBeams : Math.min(setup.physicalBeams, limit),
            launcher_count: fed
                ? setup.physicalLaunchers
                : Math.min(setup.physicalLaunchers, limit),
            bay_count: fed
                ? setup.physicalBays + (setup.physicalBays > 0 ? 3 : 0)
                : Math.min(setup.physicalBays, limit),
        },
    };
}

function materializeShip(
    ship: ShipObservationResponse,
    game: GameDetailsResponse,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    const warnings: string[] = [];
    const facts = shipFacts(ship);
    const hull = hullRecord(catalog, ship.hull_id);
    const raceId = playerRaceId(game, ship.owner_id);
    const physicalBeams = facts.beams
        ?? (hull === null ? 0 : intValue(hull, "beams", "beamcount") ?? 0);
    const physicalLaunchers = facts.tubes
        ?? (hull === null ? 0 : intValue(hull, "launchers", "torpedotubes", "tubes") ?? 0);
    const physicalBays = facts.bays
        ?? (hull === null ? 0 : intValue(hull, "fighterbays", "bays") ?? 0);
    const baseMass = hull === null ? 1 : intValue(hull, "mass") ?? 1;
    const hullCrew = hull === null ? 1 : intValue(hull, "crew") ?? 1;
    const damage = facts.damage ?? 0;
    if (facts.damage === null) warnings.push("Damage unknown: 0% is a simulation assumption.");

    const beamId = factNumber(ship.payload, "beamid", "beam_id")
        ?? componentIdByName(catalog.beams, facts.beamName)
        ?? 0;
    const torpedoId = factNumber(ship.payload, "torpedoid", "torpedo_id")
        ?? componentIdByName(catalog.torpedos, facts.torpedoName)
        ?? 0;
    if (physicalBeams > 0 && beamId === 0) warnings.push("Beam type unknown: choose a beam technology.");
    if (physicalLaunchers > 0 && torpedoId === 0) warnings.push("Torpedo type unknown: choose a torpedo technology.");

    const shieldFact = factNumber(ship.payload, "shield");
    const shield = shieldFact ?? 100;
    if (shieldFact === null) warnings.push("Shield not observed: simulator starts at 100%.");

    let fighters = facts.fighters;
    if (physicalBays > 0 && fighters === null) {
        fighters = 0;
        warnings.push("Fighter stock unknown: 0 is a simulation assumption, not a fact.");
    }
    let torpedoes = facts.torpedoes;
    if (physicalLaunchers > 0 && torpedoes === null) {
        torpedoes = 0;
        warnings.push("Torpedo stock unknown: 0 is a simulation assumption, not a fact.");
    }

    const initial: MaterializedCombatant = {
        warnings,
        setup: {
            kind: "ship",
            baseMass,
            physicalBeams,
            physicalLaunchers,
            physicalBays,
        },
        combatant: {
            source_kind: "known_ship",
            source_id: ship.ship_id,
            name: ship.name ?? facts.hullName ?? `Ship #${ship.ship_id}`,
            object_id: ship.ship_id,
            owner_id: ship.owner_id,
            race_id: raceId,
            hull_id: ship.hull_id ?? 1,
            has_starbase: false,
            physical_beam_count: physicalBeams,
            physical_launcher_count: physicalLaunchers,
            physical_bay_count: physicalBays,
            federation_crew_bonus: false,
            beam_count: physicalBeams,
            launcher_count: physicalLaunchers,
            bay_count: physicalBays,
            beam_id: beamId,
            torpedo_id: torpedoId,
            shield,
            damage,
            crew: facts.crew ?? hullCrew,
            mass: baseMass,
            torpedoes: torpedoes ?? 0,
            fighters: fighters ?? 0,
            beam_kill_rate: 1,
            beam_charge_rate: 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
    return normalizeShipForRace(initial, raceId);
}

function materializeManualHull(
    hullId: number,
    raceId: number | null,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    const hull = hullRecord(catalog, hullId);
    const physicalBeams = hull === null ? 0 : intValue(hull, "beams", "beamcount") ?? 0;
    const physicalLaunchers = hull === null ? 0 : intValue(hull, "launchers", "tubes") ?? 0;
    const physicalBays = hull === null ? 0 : intValue(hull, "fighterbays", "bays") ?? 0;
    const baseMass = hull === null ? 1 : intValue(hull, "mass") ?? 1;
    const crew = hull === null ? 1 : intValue(hull, "crew") ?? 1;
    const warnings: string[] = [];
    if (physicalBeams > 0) warnings.push("Manual hull: choose beam technology.");
    if (physicalLaunchers > 0) warnings.push("Manual hull: choose torpedo technology and ammunition.");
    if (physicalBays > 0) warnings.push("Manual hull: set fighter stock.");
    const initial: MaterializedCombatant = {
        warnings,
        setup: {
            kind: "ship",
            baseMass,
            physicalBeams,
            physicalLaunchers,
            physicalBays,
        },
        combatant: {
            source_kind: "manual",
            source_id: hullId,
            name: hull === null ? `Hull #${hullId}` : textValue(hull, "name") ?? `Hull #${hullId}`,
            object_id: null,
            owner_id: null,
            race_id: raceId,
            hull_id: hullId,
            has_starbase: false,
            physical_beam_count: physicalBeams,
            physical_launcher_count: physicalLaunchers,
            physical_bay_count: physicalBays,
            federation_crew_bonus: false,
            beam_count: physicalBeams,
            launcher_count: physicalLaunchers,
            bay_count: physicalBays,
            beam_id: 0,
            torpedo_id: 0,
            shield: 100,
            damage: 0,
            crew,
            mass: baseMass,
            torpedoes: 0,
            fighters: 0,
            beam_kill_rate: 1,
            beam_charge_rate: 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
    return normalizeShipForRace(initial, raceId);
}

export function rebuildPlanet(
    value: MaterializedCombatant,
    setup: PlanetSetup,
    raceId: number | null,
): MaterializedCombatant {
    const planetDefense = Math.max(0, Math.trunc(setup.planetDefense));
    const starbaseDefense = setup.starbasePresent
        ? Math.max(0, Math.trunc(setup.starbaseDefense))
        : 0;
    const starbaseFighters = setup.starbasePresent
        ? Math.max(0, Math.trunc(setup.starbaseFighters))
        : 0;
    const planetCanFight = planetDefense > 0;
    const planetFighters = planetCanFight
        ? Math.round(Math.sqrt(Math.max(0, planetDefense - 0.75)))
        : 0;
    const planetBays = planetCanFight ? Math.trunc(Math.sqrt(planetDefense)) : 0;
    const beamCount = planetCanFight
        ? Math.min(10, Math.round(Math.sqrt((planetDefense + starbaseDefense) / 3)))
        : 0;
    const defaultPlanetBeamTech = planetCanFight
        ? Math.max(1, Math.min(10, Math.trunc(Math.sqrt(planetDefense / 2))))
        : 0;
    const starbaseBeamTech = setup.starbasePresent
        ? Math.max(0, Math.min(10, Math.trunc(setup.starbaseBeamTech)))
        : 0;

    return {
        ...value,
        setup: {
            ...setup,
            planetDefense,
            starbaseDefense,
            starbaseFighters,
            starbaseBeamTech,
        },
        combatant: {
            ...value.combatant,
            race_id: raceId,
            has_starbase: setup.starbasePresent,
            physical_beam_count: null,
            physical_launcher_count: null,
            physical_bay_count: null,
            federation_crew_bonus: false,
            beam_count: beamCount,
            launcher_count: 0,
            bay_count: planetCanFight ? planetBays + (setup.starbasePresent ? 5 : 0) : 0,
            beam_id: beamCount > 0 ? Math.max(defaultPlanetBeamTech, starbaseBeamTech) : 0,
            torpedo_id: 0,
            shield: planetCanFight ? 100 : 0,
            damage: 0,
            crew: 10_000,
            mass: Math.max(1, 100 + planetDefense + starbaseDefense),
            torpedoes: 0,
            fighters: planetCanFight ? planetFighters + starbaseFighters : 0,
            beam_kill_rate: 1,
            beam_charge_rate: 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
        },
    };
}

function materializePlanet(
    planet: PlanetObservationResponse,
    starbase: StarbaseObservationResponse | null,
    game: GameDetailsResponse,
): MaterializedCombatant {
    const facts = planetFacts(planet);
    const baseFacts = starbase === null ? null : starbaseFacts(starbase);
    const warnings: string[] = [];
    if (facts.defense === null) warnings.push("Planet defense unknown: 0 is a simulation assumption.");
    if (starbase !== null && baseFacts?.defense === null) warnings.push("Starbase defense unknown: 0 is a simulation assumption.");
    if (starbase !== null && baseFacts?.fighters === null) warnings.push("Starbase fighters unknown: 0 is a simulation assumption.");

    const setup: PlanetSetup = {
        kind: "planet",
        planetDefense: facts.defense ?? 0,
        starbasePresent: starbase !== null,
        starbaseDefense: baseFacts?.defense ?? 0,
        starbaseBeamTech: baseFacts?.beamTech ?? 0,
        starbaseFighters: baseFacts?.fighters ?? 0,
    };
    const initial: MaterializedCombatant = {
        warnings,
        setup,
        combatant: {
            source_kind: "known_planet",
            source_id: planet.planet_id,
            name: planet.name ?? `Planet #${planet.planet_id}`,
            object_id: planet.planet_id,
            owner_id: planet.owner_id,
            race_id: playerRaceId(game, planet.owner_id) ?? starbase?.race_id ?? null,
            hull_id: 0,
            has_starbase: starbase !== null,
            physical_beam_count: null,
            physical_launcher_count: null,
            physical_bay_count: null,
            federation_crew_bonus: false,
            beam_count: 0,
            launcher_count: 0,
            bay_count: 0,
            beam_id: 0,
            torpedo_id: 0,
            shield: 100,
            damage: 0,
            crew: 10_000,
            mass: 100,
            torpedoes: 0,
            fighters: 0,
            beam_kill_rate: 1,
            beam_charge_rate: 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
    return rebuildPlanet(initial, setup, initial.combatant.race_id);
}

export function materializeCandidate(
    key: CandidateKey,
    game: GameDetailsResponse,
    intel: PrivateIntelMapResponse,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant | null {
    const [kind, rawId] = key.split(":");
    const id = Number(rawId);
    if (!Number.isInteger(id) || id <= 0) return null;
    if (kind === "ship") {
        const ship = intel.ships.find((item) => item.ship_id === id);
        return ship === undefined ? null : materializeShip(ship, game, catalog);
    }
    if (kind === "planet") {
        const planet = intel.planets.find((item) => item.planet_id === id);
        if (planet === undefined) return null;
        const starbase = intel.starbases.find((item) => item.planet_id === id) ?? null;
        return materializePlanet(planet, starbase, game);
    }
    if (kind === "hull") {
        return materializeManualHull(id, observerRaceId(game, intel), catalog);
    }
    return null;
}

export function candidateLabel(
    key: CandidateKey,
    intel: PrivateIntelMapResponse,
    catalog: GameRuleCatalogResponse,
): string {
    const [kind, rawId] = key.split(":");
    const id = Number(rawId);
    if (kind === "ship") {
        const ship = intel.ships.find((item) => item.ship_id === id);
        return ship === undefined
            ? `Ship #${id}`
            : `${ship.name ?? `Ship #${id}`} · #${id}`;
    }
    if (kind === "planet") {
        const planet = intel.planets.find((item) => item.planet_id === id);
        const hasBase = intel.starbases.some((item) => item.planet_id === id);
        return planet === undefined
            ? `Planet #${id}`
            : `${planet.name ?? `Planet #${id}`} · #${id}${hasBase ? " + base" : ""}`;
    }
    const hull = hullRecord(catalog, id);
    return `Manual · ${hull === null ? `Hull #${id}` : textValue(hull, "name") ?? `Hull #${id}`}`;
}
