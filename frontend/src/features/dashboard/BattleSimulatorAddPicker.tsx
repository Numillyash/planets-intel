import { useEffect, useMemo, useState } from "react";

import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";
import type { GameDetailsResponse } from "../../types/api";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    candidateLabel,
    hullRecord,
    intValue,
    materializeCandidate,
    normalizeShipForRace,
    observerRaceId,
    raceLabel,
    rebuildPlanet,
    textValue,
    type CandidateKey,
    type MaterializedCombatant,
    type PlanetSetup,
    type SideName,
} from "./battleSimulatorModel";


type AddSource = "known_ship" | "known_planet" | "generic";
type GenericKind = "ship" | "planet";

interface ShipGroup {
    raceId: number | null;
    label: string;
    keys: CandidateKey[];
}

interface HullChoice {
    key: CandidateKey;
    raceId: number | null;
    value: string;
}

interface HullGroup {
    raceId: number | null;
    label: string;
    choices: HullChoice[];
}


function integerIdList(value: unknown): number[] {
    const raw = Array.isArray(value)
        ? value
        : typeof value === "string"
            ? value.split(",")
            : [];
    const result: number[] = [];
    for (const item of raw) {
        const numeric = typeof item === "number"
            ? item
            : typeof item === "string" && item.trim() !== ""
                ? Number(item)
                : Number.NaN;
        if (Number.isSafeInteger(numeric) && numeric > 0) result.push(numeric);
    }
    return [...new Set(result)];
}


function raceHullIds(race: Record<string, unknown>): number[] {
    const configured = integerIdList(race.hulls);
    return configured.length > 0
        ? configured
        : integerIdList(race.basehulls);
}


function genericHullLabel(
    key: CandidateKey,
    catalog: GameRuleCatalogResponse,
): string {
    const hullId = Number(key.split(":")[1]);
    const hull = hullRecord(catalog, Number.isSafeInteger(hullId) ? hullId : null);
    return hull === null
        ? `Hull #${hullId}`
        : textValue(hull, "name") ?? `Hull #${hullId}`;
}


function hullWeaponCapacity(
    catalog: GameRuleCatalogResponse,
    hullId: number | null,
): { beams: number; launchers: number; bays: number } {
    const hull = hullRecord(catalog, hullId);
    if (hull === null) return { beams: 0, launchers: 0, bays: 0 };
    return {
        beams: Math.max(0, intValue(hull, "beams", "beamcount") ?? 0),
        launchers: Math.max(0, intValue(hull, "launchers", "torpedotubes", "tubes") ?? 0),
        bays: Math.max(0, intValue(hull, "fighterbays", "bays") ?? 0),
    };
}


function isPrimaryCombatHull(
    catalog: GameRuleCatalogResponse,
    hullId: number | null,
): boolean {
    const weapons = hullWeaponCapacity(catalog, hullId);
    // This is a picker heuristic only, never factual combat inference. It keeps
    // freighters/tankers/probes out of the default list while retaining them
    // behind "Show support ships".
    return weapons.launchers > 0 || weapons.bays > 0 || weapons.beams >= 4;
}


function materializeGenericPlanet(
    game: GameDetailsResponse,
    intel: PrivateIntelMapResponse,
): MaterializedCombatant {
    const raceId = observerRaceId(game, intel);
    const warnings = [
        "Generic planet: defense, starbase and fighter values are simulation assumptions until entered explicitly.",
    ];
    const setup: PlanetSetup = {
        kind: "planet",
        planetDefense: 0,
        starbasePresent: false,
        starbaseDefense: 0,
        starbaseBeamTech: 0,
        starbaseFighters: 0,
        starbaseDamage: 0,
        starbaseMassBonus: 0,
    };
    const initial: MaterializedCombatant = {
        warnings,
        setup,
        combatant: {
            source_kind: "manual",
            source_id: null,
            name: "Generic planet / starbase",
            object_id: null,
            owner_id: null,
            race_id: raceId,
            hull_id: 0,
            has_starbase: false,
            physical_beam_count: null,
            physical_launcher_count: null,
            physical_bay_count: null,
            federation_crew_bonus: false,
            lizard_crew_bonus: false,
            galactic_power: false,
            beam_count: 0,
            launcher_count: 0,
            bay_count: 0,
            beam_id: 0,
            torpedo_id: 0,
            shield: 0,
            damage: 0,
            crew: 10000,
            mass: 100,
            torpedoes: 0,
            fighters: 0,
            beam_kill_rate: 1,
            beam_charge_rate: 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            planet_defense: 0,
            starbase_defense: null,
            starbase_fighters: null,
            starbase_beam_tech: null,
            starbase_damage: null,
            starbase_mass_bonus: null,
            notes: warnings,
        },
    };
    return rebuildPlanet(initial, setup, raceId);
}


export function BattleSimulatorAddPicker({
    side,
    game,
    intel,
    catalog,
    onAdd,
}: {
    side: SideName;
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse;
    catalog: GameRuleCatalogResponse;
    onAdd: (combatant: MaterializedCombatant) => void;
}) {
    const [source, setSource] = useState<AddSource>("known_ship");
    const [showSupport, setShowSupport] = useState(false);
    const [shipKey, setShipKey] = useState<CandidateKey | null>(null);
    const [planetKey, setPlanetKey] = useState<CandidateKey | null>(null);
    const [hullChoiceValue, setHullChoiceValue] = useState<string | null>(null);
    const [genericKind, setGenericKind] = useState<GenericKind>("ship");

    const hullIds = useMemo<number[]>(
        () => catalog.hulls
            .map((hull) => intValue(hull, "id"))
            .filter((id): id is number => id !== null && id > 0),
        [catalog.hulls],
    );
    const hullGroups = useMemo<HullGroup[]>(() => {
        const available = new Set(hullIds);
        const assigned = new Set<number>();
        const groups: HullGroup[] = [];

        for (const race of [...catalog.races].sort(
            (left, right) => (intValue(left, "id") ?? 10_000) - (intValue(right, "id") ?? 10_000),
        )) {
            const raceId = intValue(race, "id");
            if (raceId === null || raceId <= 0) continue;
            const raceHulls = raceHullIds(race)
                .filter((hullId) => available.has(hullId));
            if (raceHulls.length === 0) continue;
            for (const hullId of raceHulls) assigned.add(hullId);
            groups.push({
                raceId,
                label: raceLabel(catalog, raceId),
                choices: raceHulls.map((hullId) => ({
                    key: `hull:${hullId}` as CandidateKey,
                    raceId,
                    value: `${raceId}:hull:${hullId}`,
                })),
            });
        }

        const unassigned = hullIds.filter((hullId) => !assigned.has(hullId));
        if (unassigned.length > 0) {
            groups.push({
                raceId: null,
                label: groups.length === 0 ? "All hulls" : "Other / unassigned",
                choices: unassigned.map((hullId) => ({
                    key: `hull:${hullId}` as CandidateKey,
                    raceId: null,
                    value: `unknown:hull:${hullId}`,
                })),
            });
        }
        return groups;
    }, [catalog, hullIds]);
    const hullChoices = useMemo(
        () => hullGroups.flatMap((group) => group.choices),
        [hullGroups],
    );
    const selectedHullChoice = useMemo(
        () => hullChoices.find((choice) => choice.value === hullChoiceValue) ?? null,
        [hullChoiceValue, hullChoices],
    );
    const planetKeys = useMemo<CandidateKey[]>(
        () => intel.planets.map((planet) => `planet:${planet.planet_id}` as CandidateKey),
        [intel.planets],
    );
    const shipGroups = useMemo<ShipGroup[]>(() => {
        const groups = new Map<string, ShipGroup>();
        for (const ship of intel.ships) {
            if (!showSupport && !isPrimaryCombatHull(catalog, ship.hull_id)) continue;
            const player = game.players.find((item) => item.slot_id === ship.owner_id) ?? null;
            const raceId = player?.race_id ?? null;
            const groupKey = raceId === null ? "unknown" : String(raceId);
            const existing = groups.get(groupKey);
            const key = `ship:${ship.ship_id}` as CandidateKey;
            if (existing !== undefined) {
                existing.keys.push(key);
            } else {
                groups.set(groupKey, {
                    raceId,
                    label: raceId === null ? "Unknown owner / race" : raceLabel(catalog, raceId),
                    keys: [key],
                });
            }
        }
        return [...groups.values()]
            .map((group) => ({
                ...group,
                keys: [...group.keys].sort((left, right) => {
                    const leftId = Number(left.split(":")[1]);
                    const rightId = Number(right.split(":")[1]);
                    return leftId - rightId;
                }),
            }))
            .sort((left, right) => {
                if (left.raceId === null) return 1;
                if (right.raceId === null) return -1;
                return left.raceId - right.raceId;
            });
    }, [catalog, game.players, intel.ships, showSupport]);
    const visibleShipKeys = useMemo(
        () => shipGroups.flatMap((group) => group.keys),
        [shipGroups],
    );

    useEffect(() => {
        if (shipKey === null || !visibleShipKeys.includes(shipKey)) {
            setShipKey(visibleShipKeys[0] ?? null);
        }
    }, [shipKey, visibleShipKeys]);
    useEffect(() => {
        if (planetKey === null || !planetKeys.includes(planetKey)) {
            setPlanetKey(planetKeys[0] ?? null);
        }
    }, [planetKey, planetKeys]);
    useEffect(() => {
        if (
            hullChoiceValue === null
            || !hullChoices.some((choice) => choice.value === hullChoiceValue)
        ) {
            setHullChoiceValue(hullChoices[0]?.value ?? null);
        }
    }, [hullChoiceValue, hullChoices]);
    useEffect(() => {
        if (side === "left" && source === "known_planet") setSource("known_ship");
        if (side === "left" && genericKind === "planet") setGenericKind("ship");
    }, [genericKind, side, source]);

    function addSelected() {
        let next: MaterializedCombatant | null = null;
        if (source === "known_ship" && shipKey !== null) {
            next = materializeCandidate(shipKey, game, intel, catalog);
        } else if (source === "known_planet" && side === "right" && planetKey !== null) {
            next = materializeCandidate(planetKey, game, intel, catalog);
        } else if (source === "generic") {
            if (genericKind === "ship" && selectedHullChoice !== null) {
                next = materializeCandidate(selectedHullChoice.key, game, intel, catalog);
                if (next !== null && selectedHullChoice.raceId !== null) {
                    next = normalizeShipForRace(next, selectedHullChoice.raceId);
                }
            } else if (genericKind === "planet" && side === "right") {
                next = materializeGenericPlanet(game, intel);
            }
        }
        if (next !== null) onAdd(next);
    }

    const canAdd = source === "known_ship"
        ? shipKey !== null
        : source === "known_planet"
            ? side === "right" && planetKey !== null
            : genericKind === "ship"
                ? selectedHullChoice !== null
                : side === "right";

    return (
        <div className="battle-sim-add-row" style={{ alignItems: "stretch", flexDirection: "column" }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button
                    className={source === "known_ship" ? "primary-button" : "secondary-button"}
                    onClick={() => setSource("known_ship")}
                    type="button"
                >
                    Known ships
                </button>
                <button
                    className={source === "known_planet" ? "primary-button" : "secondary-button"}
                    disabled={side === "left"}
                    onClick={() => setSource("known_planet")}
                    title={side === "left" ? "Planets are fixed defenders and can only be added on RIGHT" : undefined}
                    type="button"
                >
                    Known planets
                </button>
                <button
                    className={source === "generic" ? "primary-button" : "secondary-button"}
                    onClick={() => setSource("generic")}
                    type="button"
                >
                    Generic ship / planet
                </button>
            </div>

            {source === "known_ship" && (
                <>
                    <select
                        className="battle-sim-select"
                        disabled={shipKey === null}
                        onChange={(event) => setShipKey(event.target.value as CandidateKey)}
                        value={shipKey ?? ""}
                    >
                        {shipGroups.map((group) => (
                            <optgroup key={group.raceId ?? "unknown"} label={group.label}>
                                {group.keys.map((key) => (
                                    <option key={key} value={key}>
                                        {candidateLabel(key, intel, catalog)}
                                    </option>
                                ))}
                            </optgroup>
                        ))}
                    </select>
                    <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12 }}>
                        <input
                            checked={showSupport}
                            onChange={(event) => setShowSupport(event.target.checked)}
                            type="checkbox"
                        />
                        Show support ships (freighters, tankers, probes and other low-armament hulls)
                    </label>
                    {!showSupport && (
                        <small>
                            Support ships are only hidden from this picker; factual intel is unchanged.
                        </small>
                    )}
                </>
            )}

            {source === "known_planet" && side === "right" && (
                <select
                    className="battle-sim-select"
                    disabled={planetKey === null}
                    onChange={(event) => setPlanetKey(event.target.value as CandidateKey)}
                    value={planetKey ?? ""}
                >
                    {planetKeys.map((key) => (
                        <option key={key} value={key}>
                            {candidateLabel(key, intel, catalog)}
                        </option>
                    ))}
                </select>
            )}

            {source === "generic" && (
                <>
                    <div style={{ display: "flex", gap: 6 }}>
                        <button
                            className={genericKind === "ship" ? "primary-button" : "secondary-button"}
                            onClick={() => setGenericKind("ship")}
                            type="button"
                        >
                            Ship hull
                        </button>
                        <button
                            className={genericKind === "planet" ? "primary-button" : "secondary-button"}
                            disabled={side === "left"}
                            onClick={() => setGenericKind("planet")}
                            type="button"
                        >
                            Planet / starbase
                        </button>
                    </div>
                    {genericKind === "ship" ? (
                        <select
                            className="battle-sim-select"
                            disabled={selectedHullChoice === null}
                            onChange={(event) => setHullChoiceValue(event.target.value)}
                            value={hullChoiceValue ?? ""}
                        >
                            {hullGroups.map((group) => (
                                <optgroup key={group.raceId ?? "unassigned"} label={group.label}>
                                    {group.choices.map((choice) => (
                                        <option key={choice.value} value={choice.value}>
                                            {genericHullLabel(choice.key, catalog)}
                                        </option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                    ) : (
                        <small>
                            Adds a blank planet. Defense, race and optional starbase are configured after adding it.
                        </small>
                    )}
                </>
            )}

            <button
                className="secondary-button"
                disabled={!canAdd}
                onClick={addSelected}
                type="button"
            >
                + {side === "left" ? "Left" : "Right"}
            </button>
        </div>
    );
}
