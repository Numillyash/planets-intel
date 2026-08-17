import { useEffect, useMemo, useState } from "react";

import {
    runStandaloneBattle,
    runStandaloneBattleOdds,
    type BattleSimulatorCombatant,
    type BattleSimulatorOddsResponse,
    type BattleSimulatorRunResponse,
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
    factString,
    planetFacts,
    shipFacts,
    starbaseFacts,
} from "../map/observationView";


type CandidateKey = `ship:${number}` | `planet:${number}`;

interface MaterializedCombatant {
    combatant: BattleSimulatorCombatant;
    warnings: string[];
}

function intValue(record: Record<string, unknown>, ...keys: string[]): number | null {
    for (const key of keys) {
        const value = record[key];
        if (typeof value === "number" && Number.isInteger(value)) return value;
        if (typeof value === "string" && /^-?\d+$/.test(value.trim())) {
            return Number(value);
        }
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
        const direct = settings[key];
        if (typeof direct === "boolean") return direct;
        if (typeof direct === "number") return direct !== 0;
        if (typeof direct === "string") {
            const folded = direct.trim().toLowerCase();
            if (["true", "1", "yes"].includes(folded)) return true;
            if (["false", "0", "no"].includes(folded)) return false;
        }
        const match = Object.entries(settings).find(
            ([candidate]) => candidate.toLowerCase() === key.toLowerCase(),
        );
        if (match !== undefined && match[0] !== key) {
            const value = match[1];
            if (typeof value === "boolean") return value;
            if (typeof value === "number") return value !== 0;
        }
    }
    return null;
}

function numericIds(value: unknown): number[] {
    if (Array.isArray(value)) return value.flatMap((item) => numericIds(item));
    if (typeof value === "number" && Number.isInteger(value) && value > 0) {
        return [value];
    }
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

function effectiveWeaponLimit(
    raceId: number | null,
    damage: number,
    federationCrewBonus: boolean,
): number {
    if (federationCrewBonus && raceId === 1) return 99;
    const decade = Math.floor(Math.max(0, damage) / 10);
    if (raceId === 2) return Math.min(10, Math.max(0, 15 - decade));
    return Math.max(0, 10 - decade);
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

    const hullBeams = hull === null ? null : intValue(hull, "beams", "beamcount");
    const hullLaunchers = hull === null
        ? null
        : intValue(hull, "launchers", "torpedotubes", "tubes");
    const hullBays = hull === null ? null : intValue(hull, "fighterbays", "bays");
    const hullMass = hull === null ? null : intValue(hull, "mass");
    const hullCrew = hull === null ? null : intValue(hull, "crew");

    const damage = facts.damage ?? 0;
    if (facts.damage === null) warnings.push("Damage unknown: simulator assumes 0%.");

    const fedSetting = boolSetting(
        catalog.settings,
        "fedcrewbonus",
        "federationcrewbonus",
        "allowfedcrewbonus",
    );
    const federationCrewBonus = raceId === 1 && fedSetting !== false;
    if (federationCrewBonus && fedSetting === null) {
        warnings.push("Federation Crew Bonus assumed enabled from the standard racial rule.");
    }

    const physicalBeams = facts.beams ?? hullBeams ?? 0;
    const physicalLaunchers = facts.tubes ?? hullLaunchers ?? 0;
    const physicalBays = facts.bays ?? hullBays ?? 0;
    const limit = effectiveWeaponLimit(raceId, damage, federationCrewBonus);

    const beamId = factNumber(ship.payload, "beamid", "beam_id")
        ?? componentIdByName(catalog.beams, facts.beamName)
        ?? 0;
    const torpedoId = factNumber(ship.payload, "torpedoid", "torpedo_id")
        ?? componentIdByName(catalog.torpedos, facts.torpedoName)
        ?? 0;

    if (physicalBeams > 0 && beamId === 0) {
        warnings.push("Beam type unknown: choose a beam before trusting the result.");
    }
    if (physicalLaunchers > 0 && torpedoId === 0) {
        warnings.push("Torpedo type unknown: choose a torpedo before trusting the result.");
    }

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

    const shield = factNumber(ship.payload, "shield") ?? 100;
    if (factNumber(ship.payload, "shield") === null) {
        warnings.push("Shield not stored in ship observation: simulator uses turn-start 100%.");
    }

    const furyFastBeams = hasAdvantage(advantages, "2x faster beams")
        || (
            raceId === 4
            && boolSetting(catalog.settings, "fascistdoublebeams") === true
        );
    const privateerCrewKill = hasAdvantage(advantages, "3x beam crew kill")
        || (raceId === 5 && player?.active_advantages.trim() === "");
    if (raceId === 5 && player?.active_advantages.trim() === "") {
        warnings.push("Privateer 3x beam crew kill assumed from the default racial rule.");
    }

    const baseBays = federationCrewBonus && physicalBays > 0
        ? physicalBays + 3
        : physicalBays;
    const effectiveBeams = Math.min(physicalBeams, limit);
    const effectiveLaunchers = Math.min(physicalLaunchers, limit);
    const effectiveBays = federationCrewBonus
        ? baseBays
        : Math.min(baseBays, limit);

    if (damage > 0 && (
        effectiveBeams !== physicalBeams
        || effectiveLaunchers !== physicalLaunchers
        || effectiveBays !== baseBays
    )) {
        warnings.push("Damaged-ship functional weapon cap applied for this engagement.");
    }

    if (ship.hull_id === null || hull === null) {
        warnings.push("Hull catalog entry unavailable: mass/crew may need manual correction.");
    }

    return {
        warnings,
        combatant: {
            source_kind: "known_ship",
            source_id: ship.ship_id,
            name: ship.name ?? facts.hullName ?? `Ship #${ship.ship_id}`,
            object_id: ship.ship_id,
            owner_id: ship.owner_id,
            race_id: raceId,
            hull_id: ship.hull_id ?? 1,
            has_starbase: false,
            beam_count: effectiveBeams,
            launcher_count: effectiveLaunchers,
            bay_count: effectiveBays,
            beam_id: beamId,
            torpedo_id: torpedoId,
            shield,
            damage,
            crew: facts.crew ?? hullCrew ?? 1,
            mass: Math.max(1, (hullMass ?? 1) + (federationCrewBonus ? 50 : 0)),
            torpedoes: torpedoes ?? 0,
            fighters: fighters ?? 0,
            beam_kill_rate: privateerCrewKill ? 3 : 1,
            beam_charge_rate: furyFastBeams ? 2 : 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
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
    const defense = facts.defense ?? 0;
    if (facts.defense === null) {
        warnings.push("Planetary defense unknown: simulator assumes 0 posts.");
    }
    const baseDefense = base?.defense ?? 0;
    if (starbase !== null && base?.defense === null) {
        warnings.push("Starbase defense unknown: simulator assumes 0 base defense posts.");
    }
    const baseFighters = base?.fighters ?? 0;
    if (starbase !== null && base?.fighters === null) {
        warnings.push("Starbase fighter stock unknown: simulator assumes 0.");
    }

    const planetFighters = Math.round(Math.sqrt(Math.max(0, defense - 0.75)));
    const planetBays = Math.trunc(Math.sqrt(Math.max(0, defense)));
    const beamCount = Math.min(
        10,
        Math.round(Math.sqrt(Math.max(0, defense + baseDefense) / 3)),
    );
    const planetBeamSlot = defense > 0
        ? Math.max(1, Math.min(10, Math.trunc(Math.sqrt(defense / 2))))
        : 0;
    const baseBeamSlot = Math.max(0, Math.min(10, base?.beamTech ?? 0));
    const beamId = beamCount > 0 ? Math.max(planetBeamSlot, baseBeamSlot) : 0;
    const player = playerForOwner(game, planet.owner_id);
    const raceId = player?.race_id ?? starbase?.race_id ?? null;
    const advantages = activeAdvantageNames(game, catalog, planet.owner_id);
    const furyFastBeams = hasAdvantage(advantages, "2x faster beams")
        || (
            raceId === 4
            && boolSetting(catalog.settings, "fascistdoublebeams") === true
        );

    if (starbase !== null && (base?.damage ?? 0) > 0) {
        warnings.push(`Starbase currently has ${base?.damage}% damage; stored defense/tech values are used.`);
    }
    if (defense <= 0) {
        warnings.push("Planet has no known defense posts; a starbase would refuse to fight by itself.");
    }

    return {
        warnings,
        combatant: {
            source_kind: "known_planet",
            source_id: planet.planet_id,
            name: starbase === null
                ? planet.name ?? `Planet #${planet.planet_id}`
                : `${planet.name ?? `Planet #${planet.planet_id}`} + starbase`,
            object_id: planet.planet_id,
            owner_id: planet.owner_id,
            race_id: raceId,
            hull_id: 0,
            has_starbase: starbase !== null,
            beam_count: beamCount,
            launcher_count: 0,
            bay_count: planetBays + (starbase === null ? 0 : 5),
            beam_id: beamId,
            torpedo_id: 0,
            shield: defense > 0 ? 100 : 0,
            damage: 0,
            crew: 10_000,
            mass: Math.max(1, 100 + defense + baseDefense),
            torpedoes: 0,
            fighters: planetFighters + baseFighters,
            beam_kill_rate: raceId === 5 ? 3 : 1,
            beam_charge_rate: furyFastBeams ? 2 : 1,
            torp_charge_rate: 1,
            torp_miss_rate: 35,
            crew_defense_rate: 0,
            notes: warnings,
        },
    };
}

function candidateLabel(
    key: CandidateKey,
    intel: PrivateIntelMapResponse,
): string {
    const [kind, rawId] = key.split(":");
    const id = Number(rawId);
    if (kind === "ship") {
        const ship = intel.ships.find((item) => item.ship_id === id);
        return ship === undefined ? `Ship #${id}` : `${ship.name ?? `Ship #${id}`} · #${id}`;
    }
    const planet = intel.planets.find((item) => item.planet_id === id);
    const base = intel.starbases.find((item) => item.planet_id === id);
    return planet === undefined
        ? `Planet #${id}`
        : `${planet.name ?? `Planet #${id}`} · #${id}${base === undefined ? "" : " + base"}`;
}

function editableNumber(
    combatant: BattleSimulatorCombatant,
    key: keyof BattleSimulatorCombatant,
    value: number,
): BattleSimulatorCombatant {
    return { ...combatant, [key]: value };
}

function CombatantEditor({
    label,
    value,
    catalog,
    onChange,
}: {
    label: string;
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (next: MaterializedCombatant) => void;
}) {
    const combatant = value.combatant;
    const numberField = (
        title: string,
        key: keyof BattleSimulatorCombatant,
        current: number,
        min = 0,
    ) => (
        <label>
            <small>{title}</small>
            <input
                min={min}
                onChange={(event) => {
                    const parsed = Number(event.target.value);
                    if (!Number.isFinite(parsed)) return;
                    onChange({
                        ...value,
                        combatant: editableNumber(combatant, key, Math.max(min, Math.trunc(parsed))),
                    });
                }}
                type="number"
                value={current}
            />
        </label>
    );

    return (
        <section className="summary-card" style={{ display: "grid", gap: 10 }}>
            <div>
                <span>{label}</span>
                <strong style={{ display: "block", marginTop: 3 }}>
                    {combatant.name ?? "Combatant"}
                </strong>
                <small>
                    {combatant.source_kind.replace("_", " ")}
                    {combatant.source_id === null ? "" : ` · #${combatant.source_id}`}
                </small>
            </div>

            {value.warnings.length > 0 && (
                <div style={{ display: "grid", gap: 3 }}>
                    {value.warnings.map((warning) => (
                        <small key={warning} style={{ color: "#e6bd79" }}>⚠ {warning}</small>
                    ))}
                </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
                {numberField("Shield %", "shield", combatant.shield)}
                {numberField("Damage %", "damage", combatant.damage)}
                {numberField("Crew", "crew", combatant.crew)}
                {numberField("Mass", "mass", combatant.mass, 1)}
                {numberField("Beams", "beam_count", combatant.beam_count)}
                {numberField("Launchers", "launcher_count", combatant.launcher_count)}
                {numberField("Bays", "bay_count", combatant.bay_count)}
                {numberField("Torpedoes", "torpedoes", combatant.torpedoes)}
                {numberField("Fighters", "fighters", combatant.fighters)}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 8 }}>
                <label>
                    <small>Beam weapon</small>
                    <select
                        onChange={(event) => onChange({
                            ...value,
                            combatant: { ...combatant, beam_id: Number(event.target.value) },
                        })}
                        value={combatant.beam_id}
                    >
                        <option value={0}>None / unknown</option>
                        {catalog.beams.map((record) => {
                            const id = intValue(record, "id");
                            if (id === null) return null;
                            return <option key={id} value={id}>{textValue(record, "name") ?? `Beam #${id}`}</option>;
                        })}
                    </select>
                </label>
                <label>
                    <small>Torpedo weapon</small>
                    <select
                        onChange={(event) => onChange({
                            ...value,
                            combatant: { ...combatant, torpedo_id: Number(event.target.value) },
                        })}
                        value={combatant.torpedo_id}
                    >
                        <option value={0}>None / unknown</option>
                        {catalog.torpedos.map((record) => {
                            const id = intValue(record, "id");
                            if (id === null) return null;
                            return <option key={id} value={id}>{textValue(record, "name") ?? `Torpedo #${id}`}</option>;
                        })}
                    </select>
                </label>
            </div>
        </section>
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
    const [leftKey, setLeftKey] = useState<CandidateKey | null>(null);
    const [rightKey, setRightKey] = useState<CandidateKey | null>(null);
    const [left, setLeft] = useState<MaterializedCombatant | null>(null);
    const [right, setRight] = useState<MaterializedCombatant | null>(null);
    const [seed, setSeed] = useState(1);
    const [battles, setBattles] = useState(10_000);
    const [running, setRunning] = useState(false);
    const [runResult, setRunResult] = useState<BattleSimulatorRunResponse | null>(null);
    const [odds, setOdds] = useState<BattleSimulatorOddsResponse | null>(null);
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

    useEffect(() => {
        if (intel === null || shipKeys.length === 0) return;
        if (leftKey === null) {
            const ownSlot = "primary_observer" in intel
                ? intel.primary_observer.player_slot_id
                : intel.observer.player_slot_id;
            const own = intel.ships.find((ship) => ship.owner_id === ownSlot);
            setLeftKey(`ship:${own?.ship_id ?? intel.ships[0].ship_id}`);
        }
        if (rightKey === null) {
            const leftId = leftKey?.startsWith("ship:") ? Number(leftKey.slice(5)) : null;
            const enemy = intel.ships.find((ship) => ship.ship_id !== leftId);
            if (enemy !== undefined) setRightKey(`ship:${enemy.ship_id}`);
            else if (intel.planets.length > 0) setRightKey(`planet:${intel.planets[0].planet_id}`);
        }
    }, [intel, leftKey, rightKey, shipKeys.length]);

    useEffect(() => {
        if (catalog === null || intel === null || leftKey === null) return;
        const id = Number(leftKey.split(":")[1]);
        const ship = intel.ships.find((item) => item.ship_id === id);
        if (ship !== undefined) setLeft(materializeShip(ship, game, catalog));
    }, [catalog, game, intel, leftKey]);

    useEffect(() => {
        if (catalog === null || intel === null || rightKey === null) return;
        const [kind, rawId] = rightKey.split(":");
        const id = Number(rawId);
        if (kind === "ship") {
            const ship = intel.ships.find((item) => item.ship_id === id);
            if (ship !== undefined) setRight(materializeShip(ship, game, catalog));
            return;
        }
        const planet = intel.planets.find((item) => item.planet_id === id);
        if (planet === undefined) return;
        const base = intel.starbases.find((item) => item.planet_id === id) ?? null;
        setRight(materializePlanet(planet, base, game, catalog));
    }, [catalog, game, intel, rightKey]);

    function invalidate() {
        setRunResult(null);
        setOdds(null);
        setError(null);
    }

    function swapSides() {
        if (leftKey === null || rightKey === null || !rightKey.startsWith("ship:")) return;
        const oldLeft = leftKey;
        setLeftKey(rightKey as CandidateKey);
        setRightKey(oldLeft);
        invalidate();
    }

    async function runOne() {
        if (left === null || right === null) return;
        setRunning(true);
        setError(null);
        try {
            const result = await runStandaloneBattle(game.game.id, {
                left: left.combatant,
                right: right.combatant,
                seed,
                right_balance_bonus: "auto",
            });
            setRunResult(result);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle simulation failed");
        } finally {
            setRunning(false);
        }
    }

    async function runOdds() {
        if (left === null || right === null) return;
        setRunning(true);
        setError(null);
        try {
            const result = await runStandaloneBattleOdds(game.game.id, {
                left: left.combatant,
                right: right.combatant,
                battles,
            });
            setOdds(result);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle odds simulation failed");
        } finally {
            setRunning(false);
        }
    }

    if (intel === null) {
        return <div className="game-dashboard-empty">No private-intel snapshot is available for T{turn}.</div>;
    }
    if (catalogError !== null) return <div className="error-card">{catalogError}</div>;
    if (catalog === null) return <div className="loading-card">Loading combat rule catalog…</div>;
    if (shipKeys.length === 0) {
        return <div className="game-dashboard-empty">No known ships are available to place on the attacking side.</div>;
    }

    return (
        <div style={{ display: "grid", gap: 14 }}>
            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">STANDALONE · T{turn} INTEL SOURCES</div>
                        <h3 style={{ margin: "4px 0" }}>Battle setup</h3>
                        <p>
                            Pick known ships and known planets directly from the active intel snapshot.
                            A known starbase is merged into its planet automatically. Imported values remain
                            simulation inputs and never modify factual observations.
                        </p>
                    </div>
                    <button
                        className="secondary-button"
                        disabled={rightKey === null || !rightKey.startsWith("ship:")}
                        onClick={swapSides}
                        type="button"
                    >
                        Swap sides
                    </button>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, marginBottom: 12 }}>
                    <label>
                        <small>LEFT · ship</small>
                        <select
                            onChange={(event) => { setLeftKey(event.target.value as CandidateKey); invalidate(); }}
                            value={leftKey ?? ""}
                        >
                            {shipKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel)}</option>)}
                        </select>
                    </label>
                    <label>
                        <small>RIGHT · ship or planet</small>
                        <select
                            onChange={(event) => { setRightKey(event.target.value as CandidateKey); invalidate(); }}
                            value={rightKey ?? ""}
                        >
                            <optgroup label="Known ships">
                                {shipKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel)}</option>)}
                            </optgroup>
                            <optgroup label="Known planets / starbases">
                                {planetKeys.map((key) => <option key={key} value={key}>{candidateLabel(key, intel)}</option>)}
                            </optgroup>
                        </select>
                    </label>
                </div>

                {left !== null && right !== null && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                        <CombatantEditor label="LEFT" value={left} catalog={catalog} onChange={(value) => { setLeft(value); invalidate(); }} />
                        <CombatantEditor label="RIGHT" value={right} catalog={catalog} onChange={(value) => { setRight(value); invalidate(); }} />
                    </div>
                )}
            </section>

            <section className="panel">
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">SIMULATION CONTROLS</div>
                        <h3 style={{ margin: "4px 0" }}>Run combat</h3>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
                        <label>
                            <small>Single-run seed</small>
                            <input min={1} max={118} type="number" value={seed} onChange={(event) => setSeed(Math.max(1, Math.min(118, Number(event.target.value))))} />
                        </label>
                        <button className="secondary-button" disabled={running || left === null || right === null} onClick={() => void runOne()} type="button">
                            Run one
                        </button>
                        <label>
                            <small>Battles</small>
                            <input min={1} max={100000} type="number" value={battles} onChange={(event) => setBattles(Math.max(1, Math.min(100000, Math.trunc(Number(event.target.value)))))} />
                        </label>
                        <button className="primary-button" disabled={running || left === null || right === null} onClick={() => void runOdds()} type="button">
                            {running ? "Simulating…" : `Run ${battles.toLocaleString()} battles`}
                        </button>
                    </div>
                </div>
                {error !== null && <div className="error-card">{error}</div>}
            </section>

            {runResult !== null && (
                <section className="panel">
                    <div className="eyebrow">ONE BATTLE · DERIVED SIMULATION</div>
                    {!runResult.supported || runResult.left === undefined || runResult.right === undefined ? (
                        <div className="error-card">{runResult.reason ?? "Unsupported combat setup"}</div>
                    ) : (
                        <>
                            <h3>{(runResult.result ?? []).join(" + ").replaceAll("_", " ")}</h3>
                            <p>
                                Seed {runResult.start_seed} · cycles {runResult.cycles ?? "—"}
                                {runResult.right_balance?.applied ? " · right +360 KT balance bonus" : ""}
                            </p>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                                {[runResult.left, runResult.right].map((side, index) => (
                                    <div className="summary-card" key={index}>
                                        <span>{index === 0 ? "LEFT" : "RIGHT"} · {side.name ?? "Combatant"}</span>
                                        <strong>{side.destroyed ? "Destroyed" : side.captured ? "Captured" : "Survived"}</strong>
                                        <small>{side.damage}% damage · {side.shield}% shield · crew {side.crew}</small>
                                        <small>torps {side.torpedoes} · fighters {side.fighters}</small>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </section>
            )}

            {odds !== null && (
                <section className="panel" style={{ borderColor: "rgba(117, 177, 227, 0.55)" }}>
                    <div className="eyebrow">REPEATED BATTLE SIMULATION</div>
                    {!odds.supported ? (
                        <div className="error-card">{odds.reason ?? "Unsupported combat setup"}</div>
                    ) : (
                        <>
                            <h3>{odds.sample_count.toLocaleString()} battles</h3>
                            <div className="table-wrapper">
                                <table className="players-table game-object-table">
                                    <thead><tr><th>Outcome</th><th>Count</th><th>Percent</th></tr></thead>
                                    <tbody>
                                        {odds.outcomes.map((item) => (
                                            <tr key={item.outcome}>
                                                <td className="player-name">{item.outcome.replaceAll("_", " ").replaceAll("+", " + ")}</td>
                                                <td>{item.count.toLocaleString()}</td>
                                                <td>{item.percent}%</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <p style={{ color: "#91a9c8" }}>
                                Classic combat seeds are sampled repeatedly. When eligible, the HOST right-side
                                carrier-balance branch is sampled at 60%; the response records how many unique
                                deterministic terminal replays were actually required.
                            </p>
                        </>
                    )}
                </section>
            )}
        </div>
    );
}
