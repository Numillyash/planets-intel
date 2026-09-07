import type { PlayerInfo } from "../../types/api";
import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";

export const COMMON_SHIP_MISSIONS = [
    "Exploration",
    "Mine Sweep",
    "Lay Mines",
    "Kill!",
    "Sensor Sweep",
    "Land and Disassemble",
    "Try to Tow",
    "Intercept",
    "Enter Wormhole",
    "Load Artifact",
    "Transfer Artifact",
    "Beam Up",
] as const;

export interface ShipMissionGroup {
    label: string;
    missions: string[];
}

export interface ShipMissionCatalogContext {
    owner: PlayerInfo | null;
    hullId: number | null;
    shipPayload: Record<string, unknown>;
    ruleCatalog: GameRuleCatalogResponse | null;
}

function normalized(value: unknown): string {
    return typeof value === "string"
        ? value.trim().toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
        : "";
}

function integer(record: Record<string, unknown> | null, ...keys: string[]): number | null {
    if (record === null) return null;
    const folded = new Map(Object.entries(record).map(([key, value]) => [key.toLowerCase(), value]));
    for (const key of keys) {
        const value = folded.get(key.toLowerCase());
        if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
        if (typeof value === "string" && /^-?\d+$/.test(value.trim())) return Number(value.trim());
    }
    return null;
}

function booleanValue(record: Record<string, unknown> | null, ...keys: string[]): boolean | null {
    if (record === null) return null;
    const folded = new Map(Object.entries(record).map(([key, value]) => [key.toLowerCase(), value]));
    for (const key of keys) {
        const value = folded.get(key.toLowerCase());
        if (typeof value === "boolean") return value;
        if (value === 1 || value === "1" || normalized(value) === "true") return true;
        if (value === 0 || value === "0" || normalized(value) === "false") return false;
    }
    return null;
}

function recordById(records: Array<Record<string, unknown>>, id: number | null): Record<string, unknown> | null {
    if (id === null) return null;
    return records.find((record) => integer(record, "id") === id) ?? null;
}

function commaSeparatedIds(value: unknown): Set<number> {
    if (typeof value !== "string") return new Set();
    return new Set(
        value
            .split(",")
            .map((item) => Number(item.trim()))
            .filter((item) => Number.isInteger(item) && item > 0),
    );
}

function idsFromUnknown(value: unknown): Set<number> {
    if (typeof value === "string") return commaSeparatedIds(value);
    if (Array.isArray(value)) {
        return new Set(
            value
                .map((item) => typeof item === "number" ? item : Number(item))
                .filter((item) => Number.isInteger(item) && item > 0),
        );
    }
    return new Set();
}

function stringsFromSpecialFields(record: Record<string, unknown> | null): string[] {
    if (record === null) return [];
    const result: string[] = [];
    for (const [key, value] of Object.entries(record)) {
        const foldedKey = key.toLowerCase();
        if (!foldedKey.includes("special") && !foldedKey.includes("abilit")) continue;
        if (typeof value === "string") result.push(value);
        if (Array.isArray(value)) {
            for (const item of value) if (typeof item === "string") result.push(item);
        }
    }
    return result;
}

function includesPhrase(text: string, phrase: string): boolean {
    return normalized(text).includes(normalized(phrase));
}

function capabilityCount(
    payload: Record<string, unknown>,
    hull: Record<string, unknown> | null,
    payloadKeys: string[],
    hullKeys: string[],
): number | null {
    const observed = integer(payload, ...payloadKeys);
    return observed ?? integer(hull, ...hullKeys);
}

function addMission(target: Set<string>, mission: string, allowed: boolean = true): void {
    if (allowed) target.add(mission);
}

function advantageMissionNames(name: string): string[] {
    switch (normalized(name)) {
        case "build clans": return ["Build Clans"];
        case "build fighters": return ["Build Fighters"];
        case "cloak and intercept": return ["Cloak and Intercept"];
        case "dark sense": return ["Dark Sense"];
        case "destroy planet": return ["Destroy Planet"];
        case "hide in warp well": return ["Hide in Warp Well"];
        case "hisssss":
        case "hiss": return ["Hisssss!"];
        case "web mines":
        case "lay web mines":
        case "lay webmines": return ["Lay Web Mines"];
        case "pillage planet": return ["Pillage Planet"];
        case "plunder planet": return ["Plunder Planet"];
        case "move minefields": return ["Pull Minefield", "Push Minefield"];
        case "rebel ground attack": return ["Rebel Ground Attack"];
        case "repair self": return ["Repair Self"];
        case "rob ship": return ["Rob Ship"];
        case "starbase fighter transfer": return ["Send Fighters", "Receive Fighters"];
        case "super refit": return ["Super Refit"];
        case "super spy": return ["Super Spy"];
        case "swarm":
        case "swarming": return ["Swarm"];
        default: return [];
    }
}

function missionAllowedForShip(
    mission: string,
    *,
    raceId: number | null,
    hullName: string,
    hullSpecial: string,
    beams: number | null,
    launchers: number | null,
    bays: number | null,
    hullMass: number | null,
    canCloak: boolean | null,
): boolean {
    if (["Hisssss!", "Pillage Planet", "Plunder Planet", "Rob Ship"].includes(mission)) {
        return beams !== 0;
    }
    if (mission === "Lay Web Mines") return launchers !== 0;
    if (mission === "Build Fighters") {
        // Rebel fighter construction is automatic and does not need this mission.
        if (raceId === 10) return false;
        return bays !== 0;
    }
    if (mission === "Cloak and Intercept") return canCloak !== false;
    if (mission === "Hide in Warp Well") return hullMass === null || hullMass < 60;
    if (mission === "Destroy Planet") {
        return includesPhrase(hullName, "Gorbie") || includesPhrase(hullSpecial, "Destroy Planet");
    }
    if (mission === "Send Fighters" || mission === "Receive Fighters") {
        return includesPhrase(hullName, "Gorbie") || includesPhrase(hullSpecial, "Fighter Transfer");
    }
    return true;
}

function defaultRaceMissions(
    raceId: number | null,
    capabilities: {
        beams: number | null;
        launchers: number | null;
        bays: number | null;
        canCloak: boolean | null;
    },
): string[] {
    if (raceId === null) return [];
    const result = new Set<string>();
    switch (raceId) {
        case 1:
            addMission(result, "Super Refit");
            break;
        case 2:
            addMission(result, "Hisssss!", capabilities.beams !== 0);
            break;
        case 3:
            addMission(result, "Super Spy");
            addMission(result, "Cloak and Intercept", capabilities.canCloak !== false);
            break;
        case 4:
            addMission(result, "Pillage Planet", capabilities.beams !== 0);
            break;
        case 5:
            addMission(result, "Rob Ship", capabilities.beams !== 0);
            break;
        case 6:
            addMission(result, "Repair Self");
            break;
        case 7:
            addMission(result, "Lay Web Mines", capabilities.launchers !== 0);
            break;
        case 8:
            addMission(result, "Dark Sense");
            break;
        case 9:
            addMission(result, "Build Fighters", capabilities.bays !== 0);
            break;
        case 10:
            addMission(result, "Rebel Ground Attack");
            break;
        case 11:
            addMission(result, "Build Fighters", capabilities.bays !== 0);
            break;
        case 12:
            addMission(result, "Swarm");
            break;
        default:
            break;
    }
    return Array.from(result);
}

export function buildShipMissionGroups(context: ShipMissionCatalogContext): ShipMissionGroup[] {
    const { owner, hullId, shipPayload, ruleCatalog } = context;
    const hull = ruleCatalog ? recordById(ruleCatalog.hulls, hullId) : null;
    const race = ruleCatalog && owner ? recordById(ruleCatalog.races, owner.race_id) : null;
    const hullName = typeof hull?.name === "string" ? hull.name : "";
    const hullSpecial = stringsFromSpecialFields(hull).join("\n");
    const beams = capabilityCount(shipPayload, hull, ["beams", "beamcount"], ["beams"]);
    const launchers = capabilityCount(shipPayload, hull, ["tubes", "launchers", "launchercount"], ["launchers", "tubes"]);
    const bays = capabilityCount(shipPayload, hull, ["bays", "fighterbays"], ["fighterbays", "bays"]);
    const hullMass = integer(hull, "mass");
    const canCloak = booleanValue(hull, "cancloak")
        ?? (includesPhrase(hullSpecial, "Advanced Cloak")
            || includesPhrase(hullSpecial, "Blink Cloak")
            || includesPhrase(hullSpecial, "Cloaking Device")
            || normalized(hullSpecial).split(/\s+/).includes("cloak")
            ? true
            : null);

    const raceMissions = new Set(defaultRaceMissions(owner?.race_id ?? null, {
        beams,
        launchers,
        bays,
        canCloak,
    }));

    if (ruleCatalog && owner) {
        const activeIds = commaSeparatedIds(owner.active_advantages);
        for (const id of idsFromUnknown(race?.baseadvantages)) activeIds.add(id);
        for (const advantage of ruleCatalog.advantages) {
            const advantageId = integer(advantage, "id");
            if (advantageId === null || !activeIds.has(advantageId)) continue;
            const name = typeof advantage.name === "string" ? advantage.name : "";
            for (const mission of advantageMissionNames(name)) {
                addMission(raceMissions, mission, missionAllowedForShip(mission, {
                    raceId: owner.race_id,
                    hullName,
                    hullSpecial,
                    beams,
                    launchers,
                    bays,
                    hullMass,
                    canCloak,
                }));
            }
        }
    }

    const hullMissions = new Set<string>();
    if (canCloak === true) addMission(hullMissions, "Cloak");
    if (includesPhrase(hullSpecial, "Bio Scan") || includesPhrase(hullSpecial, "Bioscan")) {
        addMission(hullMissions, "Bio Scan");
    }
    if (includesPhrase(hullSpecial, "Repair Ship")) addMission(hullMissions, "Repair Ship");
    if (includesPhrase(hullSpecial, "Move Minefields")) {
        addMission(hullMissions, "Pull Minefield");
        addMission(hullMissions, "Push Minefield");
    }
    if (includesPhrase(hullSpecial, "Tantrum")) addMission(hullMissions, "Tantrum");
    if (includesPhrase(hullSpecial, "Swarm")) addMission(hullMissions, "Swarm");
    if (includesPhrase(hullSpecial, "Destroy Planet")) addMission(hullMissions, "Destroy Planet");

    // A contextual item should not be repeated in more than one group.
    const common = new Set<string>(COMMON_SHIP_MISSIONS);
    for (const mission of common) {
        raceMissions.delete(mission);
        hullMissions.delete(mission);
    }
    for (const mission of raceMissions) hullMissions.delete(mission);

    const groups: ShipMissionGroup[] = [
        { label: "Common", missions: Array.from(COMMON_SHIP_MISSIONS) },
    ];
    if (raceMissions.size > 0) {
        groups.push({ label: "Race & active advantages", missions: Array.from(raceMissions) });
    }
    if (hullMissions.size > 0) {
        groups.push({ label: "Hull abilities", missions: Array.from(hullMissions) });
    }
    return groups;
}
