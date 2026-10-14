import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";
import type { PlayerInfo } from "../../types/api";

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

interface MissionEligibilityContext {
    raceId: number | null;
    hullName: string;
    hullSpecial: string;
    beams: number | null;
    launchers: number | null;
    bays: number | null;
    hullMass: number | null;
    canCloak: boolean | null;
}

const MISSION_FIELD_NAMES = new Set([
    "mission",
    "missionname",
    "missions",
    "specialmission",
    "specialmissions",
]);

function normalized(value: unknown): string {
    return typeof value === "string"
        ? value.trim().toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
        : "";
}

function normalizedKey(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
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

function explicitMissionNames(record: Record<string, unknown> | null): string[] {
    if (record === null) return [];
    const result = new Set<string>();
    for (const [key, value] of Object.entries(record)) {
        if (!MISSION_FIELD_NAMES.has(normalizedKey(key))) continue;
        const candidates = Array.isArray(value) ? value : [value];
        for (const candidate of candidates) {
            if (typeof candidate !== "string") continue;
            const name = candidate.trim();
            if (!name || /^\d+$/.test(name)) continue;
            result.add(name);
        }
    }
    return Array.from(result);
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
    const value = mission.trim();
    if (allowed && value) target.add(value);
}

function advantageMissionNames(name: string): string[] {
    const value = normalized(name);
    if (value.includes("build clans")) return ["Build Clans"];
    if (value.includes("build fighters")) return ["Build Fighters"];
    if (value.includes("cloak and intercept")) return ["Cloak and Intercept"];
    if (value.includes("dark sense")) return ["Dark Sense"];
    if (value.includes("destroy planet")) return ["Destroy Planet"];
    if (value.includes("hide in warp well")) return ["Hide in Warp Well"];
    if (value.includes("hiss")) return ["Hisssss!"];
    if (value.includes("web mine")) return ["Lay Web Mines"];
    if (value.includes("pillage")) return ["Pillage Planet"];
    if (value.includes("plunder")) return ["Plunder Planet"];
    if (value.includes("move minefield")) return ["Pull Minefield", "Push Minefield"];
    if (value.includes("rebel ground attack")) return ["Rebel Ground Attack"];
    if (value.includes("repair self")) return ["Repair Self"];
    if (value.includes("rob ship")) return ["Rob Ship"];
    if (value.includes("fighter transfer")) return ["Send Fighters", "Receive Fighters"];
    if (value.includes("super refit")) return ["Super Refit"];
    if (value.includes("super spy")) return ["Super Spy"];
    if (value.includes("swarm")) return ["Swarm"];
    return [];
}

function missionAllowedForShip(
    mission: string,
    context: MissionEligibilityContext,
): boolean {
    const {
        raceId,
        hullName,
        hullSpecial,
        beams,
        launchers,
        bays,
        hullMass,
        canCloak,
    } = context;

    if (["Hisssss!", "Pillage Planet", "Plunder Planet", "Rob Ship"].includes(mission)) {
        return beams !== null && beams > 0;
    }
    if (mission === "Lay Web Mines") return launchers !== null && launchers > 0;
    if (mission === "Build Fighters") {
        // Rebel fighter construction is automatic and does not need this mission.
        if (raceId === 10) return false;
        return bays !== null && bays > 0;
    }
    if (mission === "Cloak and Intercept") return canCloak === true;
    if (mission === "Hide in Warp Well") return hullMass !== null && hullMass < 60;
    if (mission === "Destroy Planet") {
        return includesPhrase(hullName, "Gorbie") || includesPhrase(hullSpecial, "Destroy Planet");
    }
    if (mission === "Send Fighters" || mission === "Receive Fighters") {
        return includesPhrase(hullName, "Gorbie") || includesPhrase(hullSpecial, "Fighter Transfer");
    }
    return true;
}

export function buildShipMissionGroups(context: ShipMissionCatalogContext): ShipMissionGroup[] {
    const { owner, hullId, shipPayload, ruleCatalog } = context;
    const hull = ruleCatalog ? recordById(ruleCatalog.hulls, hullId) : null;
    const race = ruleCatalog && owner ? recordById(ruleCatalog.races, owner.race_id) : null;
    const hullNameValue = hull?.name;
    const hullName = typeof hullNameValue === "string" ? hullNameValue : "";
    const hullSpecial = stringsFromSpecialFields(hull).join("\n");
    const beams = capabilityCount(shipPayload, hull, ["beams", "beamcount"], ["beams"]);
    const launchers = capabilityCount(
        shipPayload,
        hull,
        ["tubes", "launchers", "launchercount"],
        ["launchers", "tubes"],
    );
    const bays = capabilityCount(shipPayload, hull, ["bays", "fighterbays"], ["fighterbays", "bays"]);
    const hullMass = integer(hull, "mass");
    const canCloak = booleanValue(hull, "cancloak")
        ?? (includesPhrase(hullSpecial, "Advanced Cloak")
            || includesPhrase(hullSpecial, "Blink Cloak")
            || includesPhrase(hullSpecial, "Cloaking Device")
            || normalized(hullSpecial).split(/\s+/).includes("cloak")
            ? true
            : null);

    const eligibility: MissionEligibilityContext = {
        raceId: owner?.race_id ?? null,
        hullName,
        hullSpecial,
        beams,
        launchers,
        bays,
        hullMass,
        canCloak,
    };
    const raceMissions = new Set<string>();

    // Prefer factual game configuration. Player activeadvantages and the race
    // baseadvantages list are Nu's game-specific availability evidence; this
    // deliberately avoids assuming that every classic racial ability is enabled
    // in custom/campaign games.
    if (ruleCatalog && owner) {
        const activeIds = commaSeparatedIds(owner.active_advantages);
        for (const id of idsFromUnknown(race?.baseadvantages)) activeIds.add(id);

        for (const missionName of explicitMissionNames(race)) {
            addMission(
                raceMissions,
                missionName,
                missionAllowedForShip(missionName, eligibility),
            );
        }

        for (const advantage of ruleCatalog.advantages) {
            const advantageId = integer(advantage, "id");
            if (advantageId === null || !activeIds.has(advantageId)) continue;

            const missionNames = new Set(explicitMissionNames(advantage));
            const advantageNameValue = advantage.name;
            if (typeof advantageNameValue === "string") {
                for (const missionName of advantageMissionNames(advantageNameValue)) {
                    missionNames.add(missionName);
                }
            }
            for (const missionName of missionNames) {
                addMission(
                    raceMissions,
                    missionName,
                    missionAllowedForShip(missionName, eligibility),
                );
            }
        }
    }

    const hullMissions = new Set<string>();
    for (const missionName of explicitMissionNames(hull)) {
        addMission(
            hullMissions,
            missionName,
            missionAllowedForShip(missionName, eligibility),
        );
    }
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
    for (const missionName of common) {
        raceMissions.delete(missionName);
        hullMissions.delete(missionName);
    }
    for (const missionName of raceMissions) hullMissions.delete(missionName);

    const groups: ShipMissionGroup[] = [
        { label: "Common", missions: Array.from(COMMON_SHIP_MISSIONS) },
    ];
    if (raceMissions.size > 0) {
        groups.push({
            label: "Race & active advantages",
            missions: Array.from(raceMissions).sort(),
        });
    }
    if (hullMissions.size > 0) {
        groups.push({ label: "Hull abilities", missions: Array.from(hullMissions).sort() });
    }
    return groups;
}
