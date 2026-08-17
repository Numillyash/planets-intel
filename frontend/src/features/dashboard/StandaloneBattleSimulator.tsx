import { useEffect, useMemo, useState } from "react";

import {
    runStandaloneBattle,
    runStandaloneBattleOdds,
    runStandaloneBattleSequence,
    runStandaloneBattleSequenceOdds,
    type BattleSimulatorCombatant,
    type BattleSimulatorOddsResponse,
    type BattleSimulatorRunResponse,
    type BattleSimulatorSequenceOddsResponse,
    type BattleSimulatorSequenceRunResponse,
} from "../../api/battleSimulator";
import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
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
import { CombatReplayPlayer } from "./CombatReplayPlayer";
import "./battle-simulator.css";


type CandidateKey = `ship:${number}` | `planet:${number}` | `hull:${number}`;
type SideName = "left" | "right";

type ShipSetup = {
    kind: "ship";
    baseMass: number;
    physicalBeams: number;
    physicalLaunchers: number;
    physicalBays: number;
};

type PlanetSetup = {
    kind: "planet";
    planetDefense: number;
    starbasePresent: boolean;
    starbaseDefense: number;
    starbaseBeamTech: number;
    starbaseFighters: number;
};

interface MaterializedCombatant {
    combatant: BattleSimulatorCombatant;
    warnings: string[];
    setup: ShipSetup | PlanetSetup;
}

function intValue(record: Record<string, unknown>, ...keys: string[]): number | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "number" && Number.isInteger(value)) return value;
        if (typeof value === "string" && /^-?\d+$/.test(value.trim())) return Number(value);
    }
    return null;
}

function textValue(record: Record<string, unknown>, ...keys: string[]): string | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "string" && value.trim()) return value.trim();
    }
    return null;
}

function boolSetting(settings: Record<string, unknown>, ...keys: string[]): boolean | null {
    for (const key of keys) {
        const direct = Object.entries(settings).find(
            ([candidate]) => candidate.toLowerCase() === key.toLowerCase(),
        )?.[1];
        if (typeof direct === "boolean") return direct;
        if (typeof direct === "number") return direct !== 0;
        if (typeof direct === "string") {
            const folded = direct.trim().toLowerCase();
            if (["true", "1", "yes"].includes(folded)) return true;
            if (["false", "0", "no"].includes(folded)) return false;
        }
    }
    return null;
}

function numericIds(value: unknown): number[] {
    if (Array.isArray(value)) return value.flatMap((item) => numericIds(item));
    if (typeof value === "number" && Number.isInteger(value) && value > 0) return [value];
    if (typeof value === "string") {
        return (value.match(/\d+/g) ?? [])
            .map(Number)
            .filter((item) => Number.isInteger(item) && item > 0);
    }
    return [];
}

function playerForOwner(game: GameDetailsResponse, ownerId: number | null) {
    return ownerId === null
        ? null
        : game.players.find((player) => player.slot_id === ownerId) ?? null;
}

function activeAdvantageNames(
    game: GameDetailsResponse,
    catalog: GameRuleCatalogResponse,
    ownerId: number | null,
): string[] {
    const player = playerForOwner(game, ownerId);
    if (player === null) return [];
    const active = new Set(numericIds(player.active_advantages));
    return catalog.advantages
        .filter((record) => {
            const id = intValue(record, "id");
            return id !== null && active.has(id);
        })
        .map((record) => textValue(record, "name") ?? "")
        .filter(Boolean);
}

function hasAdvantage(names: string[], needle: string): boolean {
    const folded = needle.toLowerCase();
    return names.some((name) => name.toLowerCase().includes(folded));
}

function hullRecord(
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
    const folded = name.toLowerCase();
    const record = records.find(
        (item) => textValue(item, "name")?.toLowerCase() === folded,
    );
    return record === undefined ? null : intValue(record, "id");
}

function raceLabel(catalog: GameRuleCatalogResponse, raceId: number | null): string {
    if (raceId === null) return "No racial bonus";
    const race = catalog.races.find((item) => intValue(item, "id") === raceId);
    return race === undefined
        ? `Race #${raceId}`
        : textValue(race, "name", "shortname") ?? `Race #${raceId}`;
}

function effectiveWeaponLimit(raceId: number | null, damage: number, fed: boolean): number {
    if (fed) return 10;
    const decade = Math.floor(Math.max(0, damage) / 10);
    if (raceId === 2) return Math.min(10, Math.max(0, 15 - decade));
    return Math.max(0, 10 - decade);
}

function raceRates(
    raceId: number | null,
    catalog: GameRuleCatalogResponse,
    knownAdvantages: string[] = [],
) {
    const fed = raceId === 1;
    const furySetting = boolSetting(
        catalog.settings,
        "fascistdoublebeams",
        "doublebeams",
    );
    const fury = raceId === 4 && (
        hasAdvantage(knownAdvantages, "2x faster beams") || furySetting === true
    );
    const privateerSetting = boolSetting(
        catalog.settings,
        "privateer3xbeamcrewkill",
        "priv3xbeamkill",
        "privateerbeamcrewkill",
    );
    const privateer = raceId === 5 && privateerSetting !== false;
    return { fed, fury, privateer };
}

function normalizeShipForRace(
    value: MaterializedCombatant,
    raceId: number | null,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    if (value.setup.kind !== "ship") return value;
    const rates = raceRates(raceId, catalog);
    const damage = value.combatant.damage;
    const limit = effectiveWeaponLimit(raceId, damage, rates.fed);
    const setup = value.setup;
    const combatant = {
        ...value.combatant,
        race_id: raceId,
        federation_crew_bonus: rates.fed,
        mass: Math.max(1, setup.baseMass + (rates.fed ? 50 : 0)),
        physical_beam_count: setup.physicalBeams,
        physical_launcher_count: setup.physicalLaunchers,
        physical_bay_count: setup.physicalBays,
        beam_count: rates.fed
            ? setup.physicalBeams
            : Math.min(setup.physicalBeams, limit),
        launcher_count: rates.fed
            ? setup.physicalLaunchers
            : Math.min(setup.physicalLaunchers, limit),
        bay_count: rates.fed
            ? setup.physicalBays + (setup.physicalBays > 0 ? 3 : 0)
            : Math.min(setup.physicalBays, limit),
        beam_kill_rate: rates.privateer ? 3 : 1,
        beam_charge_rate: rates.fury ? 2 : 1,
    };
    return { ...value, combatant };
}

function materializeShip(
    ship: ShipObservationResponse,
    game: GameDetailsResponse,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    const warnings: string[] = [];
    const facts = shipFacts(ship);
    const hull = hullRecord(catalog, ship.hull_id);
    const player = playerForOwner(game, ship.owner_id);
    const raceId = player?.race_id ?? null;
    const advantages = activeAdvantageNames(game, catalog, ship.owner_id);
    const physicalBeams = facts.beams ?? (hull === null ? 0 : intValue(hull, "beams", "beamcount") ?? 0);
    const physicalLaunchers = facts.tubes ?? (hull === null ? 0 : intValue(hull, "launchers", "torpedotubes", "tubes") ?? 0);
    const physicalBays = facts.bays ?? (hull === null ? 0 : intValue(hull, "fighterbays", "bays") ?? 0);
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
    if (physicalBeams > 0 && beamId === 0) warnings.push("Beam type unknown: select a beam weapon.");
    if (physicalLaunchers > 0 && torpedoId === 0) warnings.push("Torpedo type unknown: select a torpedo weapon.");

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
    const shieldFact = factNumber(ship.payload, "shield");
    const shield = shieldFact ?? 100;
    if (shieldFact === null) warnings.push("Shield not observed: simulator starts at 100%.");
    if (ship.hull_id === null || hull === null) warnings.push("Hull catalog entry unavailable; mass/crew use conservative fallbacks.");

    const rates = raceRates(raceId, catalog, advantages);
    const limit = effectiveWeaponLimit(raceId, damage, rates.fed);
    return {
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
            federation_crew_bonus: rates.fed,
            beam_count: rates.fed ? physicalBeams : Math.min(physicalBeams, limit),
            launcher_count: rates.fed ? physicalLaunchers : Math.min(physicalLaunchers, limit),
            bay_count: rates.fed
                ? physicalBays + (physicalBays > 0 ? 3 : 0)
                : Math.min(physicalBays, limit),
            beam_id: beamId,
            torpedo_id: torpedoId,
            shield,
            damage,
            crew: facts.crew ?? hullCrew,
            mass: Math.max(1, baseMass + (rates.fed ? 50 : 0)),
            torpedoes: torpedoes ?? 0,
            fighters: fighters ?? 0,
            beam_kill_rate: rates.privateer ? 3 : 1,
            beam_charge_rate: rates.fury ? 2 : 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
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
    const rates = raceRates(raceId, catalog);
    const name = hull === null
        ? `Hull #${hullId}`
        : textValue(hull, "name") ?? `Hull #${hullId}`;
    return {
        warnings,
        setup: { kind: "ship", baseMass, physicalBeams, physicalLaunchers, physicalBays },
        combatant: {
            source_kind: "manual",
            source_id: hullId,
            name,
            object_id: null,
            owner_id: null,
            race_id: raceId,
            hull_id: hullId,
            has_starbase: false,
            physical_beam_count: physicalBeams,
            physical_launcher_count: physicalLaunchers,
            physical_bay_count: physicalBays,
            federation_crew_bonus: rates.fed,
            beam_count: physicalBeams,
            launcher_count: physicalLaunchers,
            bay_count: physicalBays + (rates.fed && physicalBays > 0 ? 3 : 0),
            beam_id: 0,
            torpedo_id: 0,
            shield: 100,
            damage: 0,
            crew,
            mass: Math.max(1, baseMass + (rates.fed ? 50 : 0)),
            torpedoes: 0,
            fighters: 0,
            beam_kill_rate: rates.privateer ? 3 : 1,
            beam_charge_rate: rates.fury ? 2 : 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
}

function rebuildPlanet(
    value: MaterializedCombatant,
    setup: PlanetSetup,
    raceId: number | null,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    const defense = Math.max(0, Math.trunc(setup.planetDefense));
    const baseDefense = setup.starbasePresent
        ? Math.max(0, Math.trunc(setup.starbaseDefense))
        : 0;
    const baseFighters = setup.starbasePresent
        ? Math.max(0, Math.trunc(setup.starbaseFighters))
        : 0;
    const canFight = defense > 0;
    const planetFighters = canFight
        ? Math.round(Math.sqrt(Math.max(0, defense - 0.75)))
        : 0;
    const planetBays = canFight ? Math.trunc(Math.sqrt(defense)) : 0;
    const beamCount = canFight
        ? Math.min(10, Math.round(Math.sqrt(Math.max(0, defense + baseDefense) / 3)))
        : 0;
    const planetBeamSlot = canFight
        ? Math.max(1, Math.min(10, Math.trunc(Math.sqrt(defense / 2))))
        : 0;
    const baseBeamSlot = setup.starbasePresent
        ? Math.max(0, Math.min(10, Math.trunc(setup.starbaseBeamTech)))
        : 0;
    const rates = raceRates(raceId, catalog);
    return {
        ...value,
        setup,
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
            bay_count: canFight ? planetBays + (setup.starbasePresent ? 5 : 0) : 0,
            beam_id: beamCount > 0 ? Math.max(planetBeamSlot, baseBeamSlot) : 0,
            torpedo_id: 0,
            shield: canFight ? 100 : 0,
            mass: Math.max(1, 100 + defense + baseDefense),
            torpedoes: 0,
            fighters: canFight ? planetFighters + baseFighters : 0,
            beam_kill_rate: rates.privateer ? 3 : 1,
            beam_charge_rate: rates.fury ? 2 : 1,
        },
    };
}

function materializePlanet(
    planet: PlanetObservationResponse,
    starbase: StarbaseObservationResponse | null,
    game: GameDetailsResponse,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant {
    const warnings: string[] = [];
    const facts = planetFacts(planet);
    const base = starbase === null ? null : starbaseFacts(starbase);
    if (facts.defense === null) warnings.push("Planet defense unknown: 0 is a simulation assumption.");
    if (starbase !== null && base?.defense === null) warnings.push("Starbase defense unknown: 0 is a simulation assumption.");
    if (starbase !== null && base?.fighters === null) warnings.push("Starbase fighters unknown: 0 is a simulation assumption.");
    const player = playerForOwner(game, planet.owner_id);
    const raceId = player?.race_id ?? starbase?.race_id ?? null;
    const setup: PlanetSetup = {
        kind: "planet",
        planetDefense: facts.defense ?? 0,
        starbasePresent: starbase !== null,
        starbaseDefense: base?.defense ?? 0,
        starbaseBeamTech: base?.beamTech ?? 0,
        starbaseFighters: base?.fighters ?? 0,
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
            race_id: raceId,
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
    return rebuildPlanet(initial, setup, raceId, catalog);
}

function observerRaceId(game: GameDetailsResponse, intel: PrivateIntelMapResponse): number | null {
    const slot = "primary_observer" in intel
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
    return game.players.find((player) => player.slot_id === slot)?.race_id ?? null;
}

function candidateLabel(key: CandidateKey, intel: PrivateIntelMapResponse, catalog: GameRuleCatalogResponse): string {
    const [kind, rawId] = key.split(":");
    const id = Number(rawId);
    if (kind === "ship") {
        const ship = intel.ships.find((item) => item.ship_id === id);
        return ship === undefined ? `Ship #${id}` : `${ship.name ?? `Ship #${id}`} · #${id}`;
    }
    if (kind === "planet") {
        const planet = intel.planets.find((item) => item.planet_id === id);
        const base = intel.starbases.find((item) => item.planet_id === id);
        return planet === undefined
            ? `Planet #${id}`
            : `${planet.name ?? `Planet #${id}`} · #${id}${base === undefined ? "" : " + base"}`;
    }
    const hull = hullRecord(catalog, id);
    return `Manual · ${hull === null ? `Hull #${id}` : textValue(hull, "name") ?? `Hull #${id}`}`;
}

function materializeCandidate(
    key: CandidateKey,
    game: GameDetailsResponse,
    intel: PrivateIntelMapResponse,
    catalog: GameRuleCatalogResponse,
): MaterializedCombatant | null {
    const [kind, rawId] = key.split(":");
    const id = Number(rawId);
    if (kind === "ship") {
        const ship = intel.ships.find((item) => item.ship_id === id);
        return ship === undefined ? null : materializeShip(ship, game, catalog);
    }
    if (kind === "planet") {
        const planet = intel.planets.find((item) => item.planet_id === id);
        if (planet === undefined) return null;
        const base = intel.starbases.find((item) => item.planet_id === id) ?? null;
        return materializePlanet(planet, base, game, catalog);
    }
    return materializeManualHull(id, observerRaceId(game, intel), catalog);
}

function NumberInput({
    label,
    value,
    onChange,
    min = 0,
    max,
    disabled = false,
}: {
    label: string;
    value: number;
    onChange: (value: number) => void;
    min?: number;
    max?: number;
    disabled?: boolean;
}) {
    return (
        <label className="battle-sim-field">
            <span>{label}</span>
            <input
                className="battle-sim-input"
                disabled={disabled}
                max={max}
                min={min}
                onChange={(event) => {
                    const parsed = Number(event.target.value);
                    if (!Number.isFinite(parsed)) return;
                    const bounded = Math.max(min, max === undefined ? parsed : Math.min(max, parsed));
                    onChange(Math.trunc(bounded));
                }}
                type="number"
                value={value}
            />
        </label>
    );
}

function RaceSelect({
    raceId,
    catalog,
    onChange,
}: {
    raceId: number | null;
    catalog: GameRuleCatalogResponse;
    onChange: (raceId: number | null) => void;
}) {
    return (
        <label className="battle-sim-field">
            <span>Race / crew</span>
            <select
                className="battle-sim-select"
                onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
                value={raceId ?? ""}
            >
                <option value="">No racial bonus</option>
                {catalog.races.map((record) => {
                    const id = intValue(record, "id");
                    if (id === null) return null;
                    return <option key={id} value={id}>{textValue(record, "name", "shortname") ?? `Race #${id}`}</option>;
                })}
            </select>
        </label>
    );
}

function ShipEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    if (value.setup.kind !== "ship") return null;
    const c = value.combatant;
    const setup = value.setup;

    const updateDamage = (damage: number) => {
        const updated = { ...value, combatant: { ...c, damage } };
        onChange(normalizeShipForRace(updated, c.race_id, catalog));
    };
    const updatePhysical = (key: "physicalBeams" | "physicalLaunchers" | "physicalBays", next: number) => {
        const updated = { ...value, setup: { ...setup, [key]: next } };
        onChange(normalizeShipForRace(updated, c.race_id, catalog));
    };

    return (
        <div className="battle-sim-editor-body">
            <div className="battle-sim-fields battle-sim-fields-4">
                <RaceSelect
                    catalog={catalog}
                    onChange={(raceId) => onChange(normalizeShipForRace(value, raceId, catalog))}
                    raceId={c.race_id}
                />
                <NumberInput label="Shield %" max={100} onChange={(shield) => onChange({ ...value, combatant: { ...c, shield } })} value={c.shield} />
                <NumberInput label="Damage %" max={9999} onChange={updateDamage} value={c.damage} />
                <NumberInput label="Crew" max={100000} onChange={(crew) => onChange({ ...value, combatant: { ...c, crew } })} value={c.crew} />
            </div>

            <div className="battle-sim-derived-strip">
                <span>Hull mass <strong>{setup.baseMass} KT</strong></span>
                <span>Combat mass <strong>{c.mass} KT</strong></span>
                <span>Effective weapons <strong>{c.beam_count}B / {c.launcher_count}T / {c.bay_count} bays</strong></span>
                <span>Race <strong>{raceLabel(catalog, c.race_id)}</strong></span>
            </div>

            {setup.physicalBeams > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput label="Installed beams" max={10} onChange={(next) => updatePhysical("physicalBeams", next)} value={setup.physicalBeams} />
                    <label className="battle-sim-field battle-sim-field-wide">
                        <span>Beam weapon</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => onChange({ ...value, combatant: { ...c, beam_id: Number(event.target.value) } })}
                            value={c.beam_id}
                        >
                            <option value={0}>Unknown / none</option>
                            {catalog.beams.map((record) => {
                                const id = intValue(record, "id");
                                if (id === null) return null;
                                return <option key={id} value={id}>{textValue(record, "name") ?? `Beam #${id}`}</option>;
                            })}
                        </select>
                    </label>
                </div>
            )}

            {setup.physicalLaunchers > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput label="Installed launchers" max={10} onChange={(next) => updatePhysical("physicalLaunchers", next)} value={setup.physicalLaunchers} />
                    <label className="battle-sim-field battle-sim-field-wide">
                        <span>Torpedo weapon</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => onChange({ ...value, combatant: { ...c, torpedo_id: Number(event.target.value) } })}
                            value={c.torpedo_id}
                        >
                            <option value={0}>Unknown / none</option>
                            {catalog.torpedos.map((record) => {
                                const id = intValue(record, "id");
                                if (id === null) return null;
                                return <option key={id} value={id}>{textValue(record, "name") ?? `Torpedo #${id}`}</option>;
                            })}
                        </select>
                    </label>
                    <NumberInput label="Torpedoes" max={100000} onChange={(torpedoes) => onChange({ ...value, combatant: { ...c, torpedoes } })} value={c.torpedoes} />
                </div>
            )}

            {setup.physicalBays > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput label="Hull fighter bays" max={30} onChange={(next) => updatePhysical("physicalBays", next)} value={setup.physicalBays} />
                    <NumberInput label="Effective bays" disabled onChange={() => {}} value={c.bay_count} />
                    <NumberInput label="Fighters" max={100000} onChange={(fighters) => onChange({ ...value, combatant: { ...c, fighters } })} value={c.fighters} />
                </div>
            )}
        </div>
    );
}

function PlanetEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    if (value.setup.kind !== "planet") return null;
    const setup = value.setup;
    const c = value.combatant;
    const update = (patch: Partial<PlanetSetup>) => {
        const nextSetup = { ...setup, ...patch };
        onChange(rebuildPlanet(value, nextSetup, c.race_id, catalog));
    };

    return (
        <div className="battle-sim-editor-body">
            <div className="battle-sim-fields battle-sim-fields-4">
                <RaceSelect
                    catalog={catalog}
                    onChange={(raceId) => onChange(rebuildPlanet(value, setup, raceId, catalog))}
                    raceId={c.race_id}
                />
                <NumberInput label="Planet defense" max={1000} onChange={(planetDefense) => update({ planetDefense })} value={setup.planetDefense} />
                <label className="battle-sim-toggle-field">
                    <span>Starbase</span>
                    <input
                        checked={setup.starbasePresent}
                        onChange={(event) => update({ starbasePresent: event.target.checked })}
                        type="checkbox"
                    />
                    <strong>{setup.starbasePresent ? "Present" : "None"}</strong>
                </label>
            </div>

            {setup.starbasePresent && (
                <div className="battle-sim-fields battle-sim-fields-3">
                    <NumberInput label="Starbase defense" max={1000} onChange={(starbaseDefense) => update({ starbaseDefense })} value={setup.starbaseDefense} />
                    <label className="battle-sim-field">
                        <span>Starbase beam tech</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => update({ starbaseBeamTech: Number(event.target.value) })}
                            value={setup.starbaseBeamTech}
                        >
                            <option value={0}>0 / none</option>
                            {catalog.beams.map((record) => {
                                const id = intValue(record, "id");
                                if (id === null) return null;
                                return <option key={id} value={id}>{id} · {textValue(record, "name") ?? `Beam #${id}`}</option>;
                            })}
                        </select>
                    </label>
                    <NumberInput label="Starbase fighters" max={100000} onChange={(starbaseFighters) => update({ starbaseFighters })} value={setup.starbaseFighters} />
                </div>
            )}

            <div className="battle-sim-derived-strip">
                <span>Combat mass <strong>{c.mass} KT</strong></span>
                <span>Beams <strong>{c.beam_count}</strong></span>
                <span>Beam tech <strong>{c.beam_id || "none"}</strong></span>
                <span>Bays <strong>{c.bay_count}</strong></span>
                <span>Total fighters <strong>{c.fighters}</strong></span>
                <span>Shield <strong>{c.shield}%</strong></span>
            </div>
            {setup.planetDefense <= 0 && (
                <div className="battle-sim-warning">Planet has no defense posts; the starbase cannot fight by itself.</div>
            )}
        </div>
    );
}

function CombatantEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    return (
        <section className="battle-sim-editor">
            <header>
                <div>
                    <span className="eyebrow">SELECTED COMBATANT</span>
                    <h3>{value.combatant.name ?? "Combatant"}</h3>
                    <small>{value.combatant.source_kind.replace("_", " ")}{value.combatant.source_id === null ? "" : ` · #${value.combatant.source_id}`}</small>
                </div>
            </header>
            {value.warnings.length > 0 && (
                <div className="battle-sim-warnings">
                    {value.warnings.map((warning) => <span key={warning}>⚠ {warning}</span>)}
                </div>
            )}
            {value.setup.kind === "ship" ? (
                <ShipEditor catalog={catalog} onChange={onChange} value={value} />
            ) : (
                <PlanetEditor catalog={catalog} onChange={onChange} value={value} />
            )}
        </section>
    );
}

function QueueColumn({
    side,
    queue,
    selectedIndex,
    onSelect,
    onMove,
    onRemove,
}: {
    side: SideName;
    queue: MaterializedCombatant[];
    selectedIndex: number;
    onSelect: (index: number) => void;
    onMove: (index: number, delta: number) => void;
    onRemove: (index: number) => void;
}) {
    return (
        <section className="battle-sim-queue-column">
            <div className="battle-sim-queue-heading">
                <span>{side.toUpperCase()}</span>
                <strong>{queue.length} combatant{queue.length === 1 ? "" : "s"}</strong>
            </div>
            <div className="battle-sim-queue-list">
                {queue.map((item, index) => (
                    <button
                        className={`battle-sim-queue-card${selectedIndex === index ? " is-selected" : ""}`}
                        key={`${item.combatant.source_kind}-${item.combatant.source_id ?? "manual"}-${index}`}
                        onClick={() => onSelect(index)}
                        type="button"
                    >
                        <span className="battle-sim-order">{index + 1}</span>
                        <span className="battle-sim-queue-card-main">
                            <strong>{item.combatant.name ?? "Combatant"}</strong>
                            <small>
                                {item.setup.kind === "planet"
                                    ? `planet${item.setup.starbasePresent ? " + starbase" : ""}`
                                    : `${item.combatant.beam_count}B · ${item.combatant.launcher_count}T · ${item.combatant.bay_count} bays`}
                            </small>
                        </span>
                        <span className="battle-sim-queue-actions" onClick={(event) => event.stopPropagation()}>
                            <button disabled={index === 0} onClick={() => onMove(index, -1)} title="Move up" type="button">↑</button>
                            <button disabled={index === queue.length - 1} onClick={() => onMove(index, 1)} title="Move down" type="button">↓</button>
                            <button disabled={queue.length <= 1} onClick={() => onRemove(index)} title="Remove" type="button">×</button>
                        </span>
                    </button>
                ))}
            </div>
        </section>
    );
}

function MeanSideCard({
    label,
    name,
    side,
}: {
    label: string;
    name: string;
    side: NonNullable<BattleSimulatorOddsResponse["sides"]["left"]>;
}) {
    return (
        <article className="battle-sim-stat-card">
            <span>{label}</span>
            <h4>{name}</h4>
            <div className="battle-sim-stat-grid">
                <div><small>Survived</small><strong>{side.survived_percent}%</strong></div>
                <div><small>Destroyed</small><strong>{side.destroyed_percent}%</strong></div>
                <div><small>Captured</small><strong>{side.captured_percent}%</strong></div>
                <div><small>Avg shield</small><strong>{side.mean_final_shield}%</strong></div>
                <div><small>Avg damage</small><strong>{side.mean_final_damage}%</strong></div>
                <div><small>Avg crew</small><strong>{side.mean_final_crew}</strong></div>
                <div><small>Avg torps</small><strong>{side.mean_final_torpedoes}</strong></div>
                <div><small>Avg fighters</small><strong>{side.mean_final_fighters}</strong></div>
            </div>
        </article>
    );
}

export function StandaloneBattleSimulator({
    game,
    intel,
    turn,
}: {
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse | null;
    turn: number;
}) {
    const [catalog, setCatalog] = useState<GameRuleCatalogResponse | null>(null);
    const [catalogError, setCatalogError] = useState<string | null>(null);
    const [leftQueue, setLeftQueue] = useState<MaterializedCombatant[]>([]);
    const [rightQueue, setRightQueue] = useState<MaterializedCombatant[]>([]);
    const [selectedSide, setSelectedSide] = useState<SideName>("left");
    const [selectedLeft, setSelectedLeft] = useState(0);
    const [selectedRight, setSelectedRight] = useState(0);
    const [leftAddKey, setLeftAddKey] = useState<CandidateKey | null>(null);
    const [rightAddKey, setRightAddKey] = useState<CandidateKey | null>(null);
    const [seed, setSeed] = useState(1);
    const [battles, setBattles] = useState(10_000);
    const [running, setRunning] = useState(false);
    const [runResult, setRunResult] = useState<BattleSimulatorRunResponse | null>(null);
    const [sequenceRun, setSequenceRun] = useState<BattleSimulatorSequenceRunResponse | null>(null);
    const [odds, setOdds] = useState<BattleSimulatorOddsResponse | null>(null);
    const [sequenceOdds, setSequenceOdds] = useState<BattleSimulatorSequenceOddsResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setCatalog(null);
        setCatalogError(null);
        void getGameRuleCatalog(game.game.id)
            .then((result) => { if (!cancelled) setCatalog(result); })
            .catch((reason) => {
                if (!cancelled) setCatalogError(
                    reason instanceof Error ? reason.message : "Failed to load combat catalog",
                );
            });
        return () => { cancelled = true; };
    }, [game.game.id]);

    const shipKeys = useMemo<CandidateKey[]>(
        () => (intel?.ships ?? []).map((ship) => `ship:${ship.ship_id}` as CandidateKey),
        [intel],
    );
    const planetKeys = useMemo<CandidateKey[]>(
        () => (intel?.planets ?? []).map((planet) => `planet:${planet.planet_id}` as CandidateKey),
        [intel],
    );
    const hullKeys = useMemo<CandidateKey[]>(
        () => (catalog?.hulls ?? [])
            .map((hull) => intValue(hull, "id"))
            .filter((id): id is number => id !== null && id > 0)
            .map((id) => `hull:${id}` as CandidateKey),
        [catalog],
    );

    function invalidate() {
        setRunResult(null);
        setSequenceRun(null);
        setOdds(null);
        setSequenceOdds(null);
        setError(null);
    }

    useEffect(() => {
        if (catalog === null || intel === null || leftQueue.length > 0 || shipKeys.length === 0) return;
        const ownSlot = "primary_observer" in intel
            ? intel.primary_observer.player_slot_id
            : intel.observer.player_slot_id;
        const own = intel.ships.find((ship) => ship.owner_id === ownSlot) ?? intel.ships[0];
        const enemy = intel.ships.find((ship) => ship.ship_id !== own.ship_id);
        const left = materializeShip(own, game, catalog);
        let right: MaterializedCombatant | null = enemy === undefined
            ? null
            : materializeShip(enemy, game, catalog);
        if (right === null && intel.planets.length > 0) {
            const planet = intel.planets[0];
            right = materializePlanet(
                planet,
                intel.starbases.find((base) => base.planet_id === planet.planet_id) ?? null,
                game,
                catalog,
            );
        }
        setLeftQueue([left]);
        if (right !== null) setRightQueue([right]);
        setLeftAddKey(shipKeys[0] ?? hullKeys[0] ?? null);
        setRightAddKey(shipKeys[0] ?? planetKeys[0] ?? hullKeys[0] ?? null);
    }, [catalog, game, hullKeys, intel, leftQueue.length, planetKeys, shipKeys]);

    if (intel === null) return <div className="game-dashboard-empty">No private-intel snapshot is available for T{turn}.</div>;
    if (catalogError !== null) return <div className="error-card">{catalogError}</div>;
    if (catalog === null) return <div className="loading-card">Loading combat rule catalog…</div>;
    if (shipKeys.length === 0 && hullKeys.length === 0) return <div className="game-dashboard-empty">No ship hulls are available for simulation.</div>;

    const leftOptions = [...shipKeys, ...hullKeys];
    const rightOptions = [...shipKeys, ...planetKeys, ...hullKeys];
    const currentLeftAdd = leftAddKey ?? leftOptions[0] ?? null;
    const currentRightAdd = rightAddKey ?? rightOptions[0] ?? null;
    const multi = leftQueue.length > 1 || rightQueue.length > 1;
    const hasPlanetInSequence = multi && [...leftQueue, ...rightQueue].some((item) => item.setup.kind === "planet");
    const selected = selectedSide === "left"
        ? leftQueue[selectedLeft] ?? null
        : rightQueue[selectedRight] ?? null;

    const setSelectedValue = (next: MaterializedCombatant) => {
        if (selectedSide === "left") {
            setLeftQueue((queue) => queue.map((item, index) => index === selectedLeft ? next : item));
        } else {
            setRightQueue((queue) => queue.map((item, index) => index === selectedRight ? next : item));
        }
        invalidate();
    };

    function addCombatant(side: SideName, key: CandidateKey | null) {
        if (key === null) return;
        const item = materializeCandidate(key, game, intel, catalog);
        if (item === null) return;
        if (side === "left" && item.setup.kind === "planet") return;
        if (side === "left") {
            setLeftQueue((queue) => [...queue, item]);
            setSelectedLeft(leftQueue.length);
        } else {
            setRightQueue((queue) => [...queue, item]);
            setSelectedRight(rightQueue.length);
        }
        setSelectedSide(side);
        invalidate();
    }

    function move(side: SideName, index: number, delta: number) {
        const setter = side === "left" ? setLeftQueue : setRightQueue;
        setter((queue) => {
            const target = index + delta;
            if (target < 0 || target >= queue.length) return queue;
            const next = [...queue];
            [next[index], next[target]] = [next[target], next[index]];
            return next;
        });
        if (side === "left") setSelectedLeft(Math.max(0, index + delta));
        else setSelectedRight(Math.max(0, index + delta));
        invalidate();
    }

    function remove(side: SideName, index: number) {
        const setter = side === "left" ? setLeftQueue : setRightQueue;
        setter((queue) => queue.filter((_, itemIndex) => itemIndex !== index));
        if (side === "left") setSelectedLeft((value) => Math.max(0, Math.min(value, leftQueue.length - 2)));
        else setSelectedRight((value) => Math.max(0, Math.min(value, rightQueue.length - 2)));
        invalidate();
    }

    function swapSides() {
        if (rightQueue.some((item) => item.setup.kind === "planet")) return;
        const oldLeft = leftQueue;
        setLeftQueue(rightQueue);
        setRightQueue(oldLeft);
        setSelectedLeft(0);
        setSelectedRight(0);
        setSelectedSide("left");
        invalidate();
    }

    async function runOne() {
        if (leftQueue.length === 0 || rightQueue.length === 0) return;
        setRunning(true);
        setError(null);
        setRunResult(null);
        setSequenceRun(null);
        try {
            if (!multi) {
                const result = await runStandaloneBattle(game.game.id, {
                    left: leftQueue[0].combatant,
                    right: rightQueue[0].combatant,
                    seed,
                    right_balance_bonus: "auto",
                });
                setRunResult(result);
            } else {
                const result = await runStandaloneBattleSequence(game.game.id, {
                    left: leftQueue.map((item) => item.combatant),
                    right: rightQueue.map((item) => item.combatant),
                    seed,
                });
                setSequenceRun(result);
            }
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle simulation failed");
        } finally {
            setRunning(false);
        }
    }

    async function runOdds() {
        if (leftQueue.length === 0 || rightQueue.length === 0) return;
        setRunning(true);
        setError(null);
        setOdds(null);
        setSequenceOdds(null);
        try {
            if (!multi) {
                setOdds(await runStandaloneBattleOdds(game.game.id, {
                    left: leftQueue[0].combatant,
                    right: rightQueue[0].combatant,
                    battles,
                }));
            } else {
                setSequenceOdds(await runStandaloneBattleSequenceOdds(game.game.id, {
                    left: leftQueue.map((item) => item.combatant),
                    right: rightQueue.map((item) => item.combatant),
                    battles,
                }));
            }
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle odds simulation failed");
        } finally {
            setRunning(false);
        }
    }

    return (
        <div className="battle-sim-shell">
            <section className="battle-sim-builder">
                <header className="battle-sim-section-header">
                    <div>
                        <span className="eyebrow">BATTLE ORDER · T{turn}</span>
                        <h3>Combat queues</h3>
                        <p>Add known intel objects or manual hulls, then reorder them exactly as they should enter combat.</p>
                    </div>
                    <button className="secondary-button" disabled={rightQueue.some((item) => item.setup.kind === "planet")} onClick={swapSides} type="button">Swap sides</button>
                </header>

                <div className="battle-sim-add-grid">
                    <div className="battle-sim-add-row">
                        <select className="battle-sim-select" onChange={(event) => setLeftAddKey(event.target.value as CandidateKey)} value={currentLeftAdd ?? ""}>
                            <optgroup label="Known ships">
                                {shipKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel, catalog)}</option>)}
                            </optgroup>
                            <optgroup label="Manual hulls">
                                {hullKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel, catalog)}</option>)}
                            </optgroup>
                        </select>
                        <button className="secondary-button" onClick={() => addCombatant("left", currentLeftAdd)} type="button">+ Left</button>
                    </div>
                    <div className="battle-sim-add-row">
                        <select className="battle-sim-select" onChange={(event) => setRightAddKey(event.target.value as CandidateKey)} value={currentRightAdd ?? ""}>
                            <optgroup label="Known ships">
                                {shipKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel, catalog)}</option>)}
                            </optgroup>
                            <optgroup label="Known planets / starbases">
                                {planetKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel, catalog)}</option>)}
                            </optgroup>
                            <optgroup label="Manual hulls">
                                {hullKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel, catalog)}</option>)}
                            </optgroup>
                        </select>
                        <button className="secondary-button" onClick={() => addCombatant("right", currentRightAdd)} type="button">+ Right</button>
                    </div>
                </div>

                <div className="battle-sim-queues">
                    <QueueColumn
                        onMove={(index, delta) => move("left", index, delta)}
                        onRemove={(index) => remove("left", index)}
                        onSelect={(index) => { setSelectedSide("left"); setSelectedLeft(index); }}
                        queue={leftQueue}
                        selectedIndex={selectedSide === "left" ? selectedLeft : -1}
                        side="left"
                    />
                    <QueueColumn
                        onMove={(index, delta) => move("right", index, delta)}
                        onRemove={(index) => remove("right", index)}
                        onSelect={(index) => { setSelectedSide("right"); setSelectedRight(index); }}
                        queue={rightQueue}
                        selectedIndex={selectedSide === "right" ? selectedRight : -1}
                        side="right"
                    />
                </div>

                {hasPlanetInSequence && (
                    <div className="battle-sim-warning">
                        Multi-wave planet/starbase carry-over is deliberately disabled until separate planet-defense and starbase-defense losses are reconstructed. Single ship-vs-planet combat remains supported.
                    </div>
                )}
            </section>

            {selected !== null && (
                <CombatantEditor catalog={catalog} onChange={setSelectedValue} value={selected} />
            )}

            <section className="battle-sim-controls">
                <div>
                    <span className="eyebrow">SIMULATION CONTROLS</span>
                    <h3>{multi ? "Run battle sequence" : "Run combat"}</h3>
                </div>
                <div className="battle-sim-control-row">
                    <NumberInput label="Start seed" max={118} min={1} onChange={setSeed} value={seed} />
                    <button className="secondary-button" disabled={running || leftQueue.length === 0 || rightQueue.length === 0 || hasPlanetInSequence} onClick={() => void runOne()} type="button">
                        {running ? "Running…" : multi ? "Run sequence once" : "Run visual battle"}
                    </button>
                    <NumberInput label="Battles" max={100000} min={1} onChange={setBattles} value={battles} />
                    <button className="primary-button" disabled={running || leftQueue.length === 0 || rightQueue.length === 0 || hasPlanetInSequence} onClick={() => void runOdds()} type="button">
                        {running ? "Simulating…" : `Run ${battles.toLocaleString()} battles`}
                    </button>
                </div>
                {error !== null && <div className="error-card">{error}</div>}
            </section>

            {runResult !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">ONE BATTLE · VISUAL DERIVED SIMULATION</span>
                    {!runResult.supported ? (
                        <div className="error-card">{runResult.reason ?? "Unsupported combat setup"}</div>
                    ) : (
                        <CombatReplayPlayer
                            autoPlay
                            cycles={runResult.cycles}
                            frames={runResult.frames}
                            result={runResult.result}
                            title={`Seed ${runResult.start_seed ?? seed}${runResult.right_balance?.applied ? " · right +360 KT" : ""}`}
                        />
                    )}
                </section>
            )}

            {sequenceRun !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">ONE QUEUED RUN · DERIVED SIMULATION</span>
                    {!sequenceRun.supported ? (
                        <div className="error-card">{sequenceRun.reason ?? "Unsupported sequence"}</div>
                    ) : (
                        <>
                            <h3>Winner: {sequenceRun.winner}</h3>
                            <div className="battle-sim-engagement-list">
                                {(sequenceRun.engagements ?? []).map((engagement) => (
                                    <div key={engagement.number}>
                                        <strong>#{engagement.number} · {leftQueue[engagement.left_index]?.combatant.name} vs {rightQueue[engagement.right_index]?.combatant.name}</strong>
                                        <span>{engagement.result.join(" + ").replaceAll("_", " ")} · seed {engagement.start_seed} · {engagement.cycles} cycles{engagement.right_balance_applied ? " · +360 KT right" : ""}</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </section>
            )}

            {odds !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">REPEATED BATTLE SIMULATION</span>
                    {!odds.supported ? (
                        <div className="error-card">{odds.reason ?? "Unsupported combat setup"}</div>
                    ) : (
                        <>
                            <div className="battle-sim-result-heading"><h3>{odds.sample_count.toLocaleString()} battles</h3></div>
                            <div className="battle-sim-outcome-grid">
                                {odds.outcomes.map((item) => (
                                    <div key={item.outcome}><strong>{item.percent}%</strong><span>{item.outcome.replaceAll("_", " ").replaceAll("+", " + ")}</span><small>{item.count.toLocaleString()} battles</small></div>
                                ))}
                            </div>
                            {odds.sides.left !== undefined && odds.sides.right !== undefined && (
                                <div className="battle-sim-mean-grid">
                                    <MeanSideCard label="LEFT · MEAN TERMINAL STATE" name={leftQueue[0]?.combatant.name ?? "Left"} side={odds.sides.left} />
                                    <MeanSideCard label="RIGHT · MEAN TERMINAL STATE" name={rightQueue[0]?.combatant.name ?? "Right"} side={odds.sides.right} />
                                </div>
                            )}
                        </>
                    )}
                </section>
            )}

            {sequenceOdds !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">REPEATED QUEUED SIMULATION</span>
                    {!sequenceOdds.supported ? (
                        <div className="error-card">{sequenceOdds.reason ?? "Unsupported sequence"}</div>
                    ) : (
                        <>
                            <h3>{sequenceOdds.sample_count.toLocaleString()} full simulations</h3>
                            <div className="battle-sim-outcome-grid">
                                {(sequenceOdds.outcomes ?? []).map((item) => (
                                    <div key={item.outcome}><strong>{item.percent}%</strong><span>{item.outcome} wins</span><small>{item.count.toLocaleString()}</small></div>
                                ))}
                            </div>
                            <div className="battle-sim-sequence-stats">
                                {(["left", "right"] as const).map((side) => (
                                    <div key={side}>
                                        <h4>{side.toUpperCase()} queue</h4>
                                        {(sequenceOdds.sides?.[side] ?? []).map((item) => (
                                            <article className="battle-sim-stat-card" key={item.index}>
                                                <span>#{item.index + 1} · fought {item.fought_percent}%</span>
                                                <h4>{item.name ?? `Combatant ${item.index + 1}`}</h4>
                                                <div className="battle-sim-stat-grid">
                                                    <div><small>Avg shield</small><strong>{item.mean_final_shield ?? "—"}%</strong></div>
                                                    <div><small>Avg damage</small><strong>{item.mean_final_damage ?? "—"}%</strong></div>
                                                    <div><small>Avg crew</small><strong>{item.mean_final_crew ?? "—"}</strong></div>
                                                    <div><small>Avg torps</small><strong>{item.mean_final_torpedoes ?? "—"}</strong></div>
                                                    <div><small>Avg fighters</small><strong>{item.mean_final_fighters ?? "—"}</strong></div>
                                                </div>
                                            </article>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </section>
            )}
        </div>
    );
}
