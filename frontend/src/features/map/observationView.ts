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
        if (Object.prototype.hasOwnProperty.call(payload, key)) {
            return payload[key];
        }
    }

    const normalizedKeys = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, item] of Object.entries(payload)) {
        if (normalizedKeys.has(key.toLowerCase())) {
            return item;
        }
    }

    return undefined;
}

export function factNumber(payload: Payload, ...keys: string[]): number | null {
    const item = value(payload, ...keys);
    if (typeof item === "number" && Number.isFinite(item)) {
        return item;
    }
    if (typeof item === "string" && item.trim() !== "") {
        const parsed = Number(item);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}

export function factString(payload: Payload, ...keys: string[]): string | null {
    const item = value(payload, ...keys);
    if (typeof item === "string" && item.trim() !== "") {
        return item.trim();
    }
    if (typeof item === "number" && Number.isFinite(item)) {
        return String(item);
    }
    return null;
}

function firstDisplayValue(
    payload: Payload,
    stringKeys: string[],
    numberKeys: string[],
    numericPrefix: string,
): string | null {
    const named = factString(payload, ...stringKeys);
    if (named !== null) {
        return named;
    }

    const numeric = factNumber(payload, ...numberKeys);
    if (numeric === null || numeric === 0) {
        return null;
    }
    return `${numericPrefix} ${numeric}`;
}

function mineralFacts(payload: Payload, mineral: string): MineralFacts {
    return {
        surface: factNumber(payload, mineral),
        ground: factNumber(
            payload,
            `ground${mineral}`,
            `${mineral}ground`,
            `${mineral}_ground`,
        ),
        density: factNumber(
            payload,
            `density${mineral}`,
            `${mineral}density`,
            `${mineral}_density`,
        ),
        production: factNumber(
            payload,
            `${mineral}production`,
            `${mineral}produced`,
            `${mineral}rate`,
            `${mineral}_production`,
        ),
    };
}

export function planetFacts(planet: PlanetObservationResponse): PlanetFacts {
    const payload = planet.payload;

    const facts: Omit<PlanetFacts, "knownFieldCount"> = {
        temperature: factNumber(payload, "temp", "temperature"),
        mines: factNumber(payload, "mines"),
        factories: factNumber(payload, "factories"),
        defense: factNumber(payload, "defense", "defenseposts", "defense_posts"),
        supplies: factNumber(payload, "supplies"),
        megacredits: factNumber(payload, "megacredits", "money", "mc"),
        clans: factNumber(payload, "clans", "colonistclans", "colonists"),
        colonistHappiness: factNumber(
            payload,
            "colonisthappypoints",
            "colonisthappiness",
            "colonisthappy",
        ),
        colonistTaxRate: factNumber(
            payload,
            "colonisttaxrate",
            "colonisttax",
        ),
        nativeRace: firstDisplayValue(
            payload,
            ["nativeracename", "native_race_name"],
            ["nativerace", "nativeraceid", "native_race_id"],
            "Race",
        ),
        nativeClans: factNumber(payload, "nativeclans", "native_clans"),
        nativeGovernment: firstDisplayValue(
            payload,
            ["nativegovernmentname", "native_government_name"],
            ["nativegovernment", "nativegovernmentid", "native_government"],
            "Government",
        ),
        nativeHappiness: factNumber(
            payload,
            "nativehappypoints",
            "nativehappiness",
            "nativehappy",
        ),
        nativeTaxRate: factNumber(payload, "nativetaxrate", "nativetax"),
        neutronium: mineralFacts(payload, "neutronium"),
        duranium: mineralFacts(payload, "duranium"),
        tritanium: mineralFacts(payload, "tritanium"),
        molybdenum: mineralFacts(payload, "molybdenum"),
    };

    const scalarValues = [
        facts.temperature,
        facts.mines,
        facts.factories,
        facts.defense,
        facts.supplies,
        facts.megacredits,
        facts.clans,
        facts.colonistHappiness,
        facts.colonistTaxRate,
        facts.nativeRace,
        facts.nativeClans,
        facts.nativeGovernment,
        facts.nativeHappiness,
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
        knownFieldCount: [...scalarValues, ...mineralValues].filter(
            (item) => item !== null,
        ).length,
    };
}

export function shipFacts(ship: ShipObservationResponse): ShipFacts {
    const payload = ship.payload;
    return {
        hullName: factString(payload, "hullname", "hull_name"),
        engineName: factString(payload, "enginename", "engine_name"),
        engineId: factNumber(payload, "engineid", "engine_id"),
        beams: factNumber(payload, "beams", "beamcount", "beam_count"),
        beamName: factString(payload, "beamname", "beam_name"),
        tubes: factNumber(payload, "tubes", "torpedotubes", "tube_count"),
        torpedoName: factString(payload, "torpedoname", "torpedo_name"),
        bays: factNumber(payload, "bays", "fighterbays", "baycount"),
        damage: factNumber(payload, "damage"),
        crew: factNumber(payload, "crew"),
        mission: firstDisplayValue(
            payload,
            ["missionname", "mission_name"],
            ["mission"],
            "Mission",
        ),
        fuel: factNumber(payload, "neutronium", "fuel"),
        clans: factNumber(payload, "clans", "colonists"),
        supplies: factNumber(payload, "supplies"),
        megacredits: factNumber(payload, "megacredits", "money"),
        duranium: factNumber(payload, "duranium"),
        tritanium: factNumber(payload, "tritanium"),
      molybdenum: factNumber(payload, "molybdenum"),
        torpedoes: factNumber(payload, "torpedoes", "torps"),
        fighters: factNumber(payload, "fighters"),
        waypointX: factNumber(payload, "waypointx", "targetx", "waypoint_x"),
        waypointY: factNumber(payload, "waypointy", "targety", "waypoint_y"),
    };
}

export function starbaseFacts(starbase: StarbaseObservationResponse): StarbaseFacts {
    const payload = starbase.payload;
    return {
        name: factString(payload, "name", "starbasename", "starbase_name"),
        damage: factNumber(payload, "damage"),
        defense: factNumber(payload, "defense"),
        fighters: factNumber(payload, "fighters"),
        beamTech: factNumber(payload, "beamtechlevel", "beamtech", "beam_tech"),
        engineTech: factNumber(payload, "enginetechlevel", "enginetech", "engine_tech"),
        hullTech: factNumber(payload, "hulltechlevel", "hulltech", "hull_tech"),
        torpedoTech: factNumber(payload, "torptechlevel", "torpedotechlevel", "torp_tech"),
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
