import type {
    PlanetObservationResponse,
    ShipObservationResponse,
    StarbaseObservationResponse,
} from "../../types/api";

export interface MineralFacts {
    surface: number | null;
    ground: number | null;
    density: number | null;
    production: number | null;
}

export interface PlanetFacts {
    friendlyCode: string | null;
    temperature: number | null;
    mines: number | null;
    factories: number | null;
    defense: number | null;
    supplies: number | null;
    megacredits: number | null;
    clans: number | null;
    colonistHappiness: number | null;
    colonistTaxRate: number | null;
    nativeRace: string | null;
    nativeClans: number | null;
    nativeGovernment: string | null;
    nativeHappiness: number | null;
    nativeTaxRate: number | null;
    neutronium: MineralFacts;
    duranium: MineralFacts;
    tritanium: MineralFacts;
    molybdenum: MineralFacts;
    knownFieldCount: number;
}

export interface ShipFacts {
    friendlyCode: string | null;
    hullName: string | null;
    engineName: string | null;
    engineId: number | null;
    beams: number | null;
    beamName: string | null;
    tubes: number | null;
    torpedoName: string | null;
    bays: number | null;
    damage: number | null;
    crew: number | null;
    mission: string | null;
    fuel: number | null;
    clans: number | null;
    supplies: number | null;
    megacredits: number | null;
    duranium: number | null;
    tritanium: number | null;
    molybdenum: number | null;
    torpedoes: number | null;
    fighters: number | null;
    waypointX: number | null;
    waypointY: number | null;
}

export interface StarbaseFacts {
    name: string | null;
    damage: number | null;
    defense: number | null;
    fighters: number | null;
    beamTech: number | null;
    engineTech: number | null;
    hullTech: number | null;
    torpedoTech: number | null;
}

type Payload = Record<string, unknown>;

function value(payload: Payload, ...keys: string[]): unknown {
    for (const key of keys) {
        if (Object.prototype.hasOwnProperty.call(payload, key)) return payload[key];
    }
    const normalizedKeys = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, item] of Object.entries(payload)) {
        if (normalizedKeys.has(key.toLowerCase())) return item;
    }
    return undefined;
}

export function factNumber(payload: Payload, ...keys: string[]): number | null {
    const item = value(payload, ...keys);
    if (typeof item === "number" && Number.isFinite(item)) return item;
    if (typeof item === "string" && item.trim() !== "") {
        const parsed = Number(item);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}

function nonNegativeFactNumber(payload: Payload, ...keys: string[]): number | null {
    const item = factNumber(payload, ...keys);
    return item !== null && item >= 0 ? item : null;
}

function positiveFactNumber(payload: Payload, ...keys: string[]): number | null {
    const item = factNumber(payload, ...keys);
    return item !== null && item > 0 ? item : null;
}

export function factString(payload: Payload, ...keys: string[]): string | null {
    const item = value(payload, ...keys);
    if (typeof item === "string" && item.trim() !== "") return item.trim();
    if (typeof item === "number" && Number.isFinite(item)) return String(item);
    return null;
}

function firstDisplayValue(
    payload: Payload,
    stringKeys: string[],
    numberKeys: string[],
    numericPrefix: string,
): string | null {
    const named = factString(payload, ...stringKeys);
    if (named !== null) return named;
    const numeric = factNumber(payload, ...numberKeys);
    if (numeric === null || numeric <= 0) return null;
    return `${numericPrefix} ${numeric}`;
}

function mineralFacts(payload: Payload, mineral: string): MineralFacts {
    return {
        surface: nonNegativeFactNumber(payload, mineral),
        ground: nonNegativeFactNumber(payload, `ground${mineral}`, `${mineral}ground`, `${mineral}_ground`),
        density: nonNegativeFactNumber(payload, `density${mineral}`, `${mineral}density`, `${mineral}_density`),
        production: nonNegativeFactNumber(payload, `${mineral}production`, `${mineral}produced`, `${mineral}rate`, `${mineral}_production`),
    };
}

export function planetFacts(planet: PlanetObservationResponse): PlanetFacts {
    const payload = planet.payload;
    const facts: Omit<PlanetFacts, "knownFieldCount"> = {
        friendlyCode: factString(payload, "friendlycode", "friendly_code", "fcode"),
        temperature: nonNegativeFactNumber(payload, "temp", "temperature"),
        mines: nonNegativeFactNumber(payload, "mines"),
        factories: nonNegativeFactNumber(payload, "factories"),
        defense: nonNegativeFactNumber(payload, "defense", "defenseposts", "defense_posts"),
        supplies: nonNegativeFactNumber(payload, "supplies"),
        megacredits: nonNegativeFactNumber(payload, "megacredits", "money", "mc"),
        clans: nonNegativeFactNumber(payload, "clans", "colonistclans", "colonists"),
        colonistHappiness: factNumber(payload, "colonisthappypoints", "colonisthappiness", "colonisthappy"),
        colonistTaxRate: nonNegativeFactNumber(payload, "colonisttaxrate", "colonisttax"),
        nativeRace: firstDisplayValue(payload, ["nativeracename", "native_race_name"], ["nativerace", "nativeraceid", "native_race_id"], "Race"),
        nativeClans: nonNegativeFactNumber(payload, "nativeclans", "native_clans"),
        nativeGovernment: firstDisplayValue(payload, ["nativegovernmentname", "native_government_name"], ["nativegovernment", "nativegovernmentid", "native_government"], "Government"),
        nativeHappiness: factNumber(payload, "nativehappypoints", "nativehappiness", "nativehappy"),
        nativeTaxRate: nonNegativeFactNumber(payload, "nativetaxrate", "nativetax"),
        neutronium: mineralFacts(payload, "neutronium"),
        duranium: mineralFacts(payload, "duranium"),
        tritanium: mineralFacts(payload, "tritanium"),
        molybdenum: mineralFacts(payload, "molybdenum"),
    };

    const scalarValues = [
        facts.friendlyCode, facts.temperature, facts.mines, facts.factories,
        facts.defense, facts.supplies, facts.megacredits, facts.clans,
        facts.colonistHappiness, facts.colonistTaxRate, facts.nativeRace,
        facts.nativeClans, facts.nativeGovernment, facts.nativeHappiness,
        facts.nativeTaxRate,
    ];
    const mineralValues = Object.values({
        neutronium: facts.neutronium,
        duranium: facts.duranium,
        tritanium: facts.tritanium,
        molybdenum: facts.molybdenum,
    }).flatMap((mineral) => Object.values(mineral));

    return {
        ...facts,
        knownFieldCount: [...scalarValues, ...mineralValues].filter((item) => item !== null).length,
    };
}

export function shipFacts(ship: ShipObservationResponse): ShipFacts {
    const payload = ship.payload;
    return {
        friendlyCode: factString(payload, "friendlycode", "friendly_code", "fcode"),
        hullName: factString(payload, "hullname", "hull_name"),
        engineName: factString(payload, "enginename", "engine_name"),
        engineId: positiveFactNumber(payload, "engineid", "engine_id"),
        beams: nonNegativeFactNumber(payload, "beams", "beamcount", "beam_count"),
        beamName: factString(payload, "beamname", "beam_name"),
        tubes: nonNegativeFactNumber(payload, "tubes", "torpedotubes", "tube_count"),
        torpedoName: factString(payload, "torpedoname", "torpedo_name"),
        bays: nonNegativeFactNumber(payload, "bays", "fighterbays", "baycount"),
        damage: nonNegativeFactNumber(payload, "damage"),
        crew: nonNegativeFactNumber(payload, "crew"),
        mission: firstDisplayValue(payload, ["missionname", "mission_name"], ["mission"], "Mission"),
        fuel: nonNegativeFactNumber(payload, "neutronium", "fuel"),
        clans: nonNegativeFactNumber(payload, "clans", "colonists"),
        supplies: nonNegativeFactNumber(payload, "supplies"),
        megacredits: nonNegativeFactNumber(payload, "megacredits", "money"),
        duranium: nonNegativeFactNumber(payload, "duranium"),
        tritanium: nonNegativeFactNumber(payload, "tritanium"),
        molybdenum: nonNegativeFactNumber(payload, "molybdenum"),
        torpedoes: nonNegativeFactNumber(payload, "torpedoes", "torps"),
        fighters: nonNegativeFactNumber(payload, "fighters"),
        waypointX: nonNegativeFactNumber(payload, "waypointx", "targetx", "waypoint_x"),
        waypointY: nonNegativeFactNumber(payload, "waypointy", "targety", "waypoint_y"),
    };
}

export function starbaseFacts(starbase: StarbaseObservationResponse): StarbaseFacts {
    const payload = starbase.payload;
    return {
        name: factString(payload, "name", "starbasename", "starbase_name"),
        damage: nonNegativeFactNumber(payload, "damage"),
        defense: nonNegativeFactNumber(payload, "defense"),
        fighters: nonNegativeFactNumber(payload, "fighters"),
        beamTech: positiveFactNumber(payload, "beamtechlevel", "beamtech", "beam_tech"),
        engineTech: positiveFactNumber(payload, "enginetechlevel", "enginetech", "engine_tech"),
        hullTech: positiveFactNumber(payload, "hulltechlevel", "hulltech", "hull_tech"),
        torpedoTech: positiveFactNumber(payload, "torptechlevel", "torpedotechlevel", "torp_tech"),
    };
}

export function formatInteger(value: number | null): string {
    return value === null ? "—" : Math.round(value).toLocaleString();
}

export function formatPercent(value: number | null): string {
    return value === null ? "—" : `${Math.round(value)}%`;
}

export function formatTemperature(value: number | null): string {
    return value === null ? "—" : `${Math.round(value)}°`;
}
