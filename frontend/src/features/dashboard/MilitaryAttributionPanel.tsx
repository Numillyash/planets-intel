import { useEffect, useMemo, useState } from "react";

import { getHistoricalCombinedIntel } from "../../api/history";
import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
import type {
    GameDetailsResponse,
    ScoreHistoryItem,
    ScoreHistoryResponse,
} from "../../types/api";
import type {
    CombinedPrivateIntelResponse,
    MapPlanetObservation,
    MapShipObservation,
    MapStarbaseObservation,
    MapStellarCartographyObservation,
} from "../../types/intel";

const MOBILE_FIGHTER_SCORE = 125;
const STARBASE_FIGHTER_SCORE = 62.5;
const PLANET_DEFENSE_SCORE = 5.5;
const STARBASE_DEFENSE_SCORE = 7.5;
const MINE_UNIT_SCORE = 0.27;

type Payload = Record<string, unknown>;

function numberField(payload: Payload, ...keys: string[]): number | null {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, value] of Object.entries(payload)) {
        if (!wanted.has(key.toLowerCase())) continue;
        if (typeof value === "number" && Number.isFinite(value)) return value;
        if (typeof value === "string" && value.trim()) {
            const parsed = Number(value);
            if (Number.isFinite(parsed)) return parsed;
        }
    }
    return null;
}

function integerField(payload: Payload, ...keys: string[]): number | null {
    const value = numberField(payload, ...keys);
    return value !== null && Number.isInteger(value) ? value : null;
}

function recordNumber(record: Record<string, unknown>, ...keys: string[]): number | null {
    return numberField(record, ...keys);
}

function recordString(record: Record<string, unknown>, ...keys: string[]): string | null {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, value] of Object.entries(record)) {
        if (!wanted.has(key.toLowerCase())) continue;
        if (typeof value === "string" && value.trim()) return value.trim();
    }
    return null;
}

function formatScore(value: number): string {
    return Math.round(value).toLocaleString();
}

function formatSigned(value: number): string {
    const rounded = Math.round(value);
    return `${rounded > 0 ? "+" : ""}${rounded.toLocaleString()}`;
}

function planetDefense(planet: MapPlanetObservation): number | null {
    return integerField(planet.payload, "defense", "defenseposts", "defense_posts");
}

function baseFighters(base: MapStarbaseObservation): number | null {
    return integerField(base.payload, "fighters");
}

function baseDefense(base: MapStarbaseObservation): number | null {
    return integerField(base.payload, "defense", "defenseposts", "defense_posts");
}

function mineOwner(field: MapStellarCartographyObservation): number | null {
    return integerField(field.payload, "ownerid", "owner_id", "owner");
}

function mineUnits(field: MapStellarCartographyObservation): number | null {
    return numberField(field.payload, "mineunits", "mine_units", "units", "mines");
}

function byId<T>(items: T[], id: (item: T) => number): Map<number, T> {
    return new Map(items.map((item) => [id(item), item]));
}

function hullMap(catalog: GameRuleCatalogResponse | null) {
    const result = new Map<number, Record<string, unknown>>();
    for (const hull of catalog?.hulls ?? []) {
        const id = recordNumber(hull, "id");
        if (id !== null && Number.isInteger(id)) result.set(id, hull);
    }
    return result;
}

function shipFighters(
    ship: MapShipObservation,
    hulls: Map<number, Record<string, unknown>>,
): number | null {
    const explicit = integerField(ship.payload, "fighters");
    if (explicit !== null) return explicit;
    if (ship.hull_id === null) return null;

    const hull = hulls.get(ship.hull_id);
    if (hull === undefined) return null;
    const bays = recordNumber(hull, "fighterbays", "bays");
    if (bays === null || bays <= 0) return null;

    // Nu private ship payloads expose one generic combat-ammo count. Combined
    // intel only preserves that field when the source observer owns the ship,
    // so a remaining ammo value is factual and may be interpreted as fighters
    // once the hull catalog proves the ship has fighter bays.
    return integerField(ship.payload, "ammo");
}

function hullMilitaryFloor(hull: Record<string, unknown> | undefined): number | null {
    if (hull === undefined) return null;
    const mc = recordNumber(hull, "cost", "mc");
    const dur = recordNumber(hull, "duranium");
    const tri = recordNumber(hull, "tritanium");
    const mol = recordNumber(hull, "molybdenum");
    if (mc === null || dur === null || tri === null || mol === null) return null;
    return mc + 5 * (dur + tri + mol);
}

function hullIsCombat(hull: Record<string, unknown> | undefined): boolean {
    if (hull === undefined) return false;
    return (recordNumber(hull, "beams") ?? 0) > 0
        || (recordNumber(hull, "launchers", "torps") ?? 0) > 0
        || (recordNumber(hull, "fighterbays", "bays") ?? 0) > 0;
}

interface Attribution {
    mobileFighterDelta: number;
    starbaseFighterDelta: number;
    planetDefenseDelta: number;
    starbaseDefenseDelta: number;
    minefieldDelta: number;
    explainedDelta: number;
    currentObservedMobileFighters: number;
    currentObservedMobileFighterScore: number;
    comparableShipFighterRecords: number;
    newlyObservedCombatShips: Array<{
        shipId: number;
        name: string;
        hullId: number | null;
        hullName: string;
        hullFloor: number | null;
        fighters: number | null;
    }>;
}

function calculateAttribution(
    slotId: number,
    current: CombinedPrivateIntelResponse,
    previous: CombinedPrivateIntelResponse,
    catalog: GameRuleCatalogResponse | null,
): Attribution {
    const hulls = hullMap(catalog);
    const previousShips = byId(previous.ships, (ship) => ship.ship_id);
    let mobileFighterDelta = 0;
    let comparableShipFighterRecords = 0;
    let currentObservedMobileFighters = 0;

    for (const ship of current.ships) {
        if (ship.owner_id !== slotId) continue;
        const fighters = shipFighters(ship, hulls);
        if (fighters !== null) currentObservedMobileFighters += fighters;

        const old = previousShips.get(ship.ship_id);
        if (
            old === undefined
            || old.owner_id !== slotId
            || old.hull_id !== ship.hull_id
        ) continue;
        const oldFighters = shipFighters(old, hulls);
        if (fighters === null || oldFighters === null) continue;
        mobileFighterDelta += (fighters - oldFighters) * MOBILE_FIGHTER_SCORE;
        comparableShipFighterRecords += 1;
    }

    const currentPlanets = current.planets.filter((planet) => planet.owner_id === slotId);
    const previousPlanets = byId(previous.planets, (planet) => planet.planet_id);
    let planetDefenseDelta = 0;
    for (const planet of currentPlanets) {
        const old = previousPlanets.get(planet.planet_id);
        if (old === undefined || old.owner_id !== slotId) continue;
        const nowDefense = planetDefense(planet);
        const oldDefense = planetDefense(old);
        if (nowDefense === null || oldDefense === null) continue;
        planetDefenseDelta += (nowDefense - oldDefense) * PLANET_DEFENSE_SCORE;
    }

    const currentPlanetOwners = new Map(current.planets.map((planet) => [planet.planet_id, planet.owner_id]));
    const previousPlanetOwners = new Map(previous.planets.map((planet) => [planet.planet_id, planet.owner_id]));
    const previousBases = byId(previous.starbases, (base) => base.starbase_id);
    let starbaseFighterDelta = 0;
    let starbaseDefenseDelta = 0;
    for (const base of current.starbases) {
        if (base.planet_id === null || currentPlanetOwners.get(base.planet_id) !== slotId) continue;
        const old = previousBases.get(base.starbase_id);
        if (
            old === undefined
            || old.planet_id === null
            || previousPlanetOwners.get(old.planet_id) !== slotId
        ) continue;
        const nowFighters = baseFighters(base);
        const oldFighters = baseFighters(old);
        if (nowFighters !== null && oldFighters !== null) {
            starbaseFighterDelta += (nowFighters - oldFighters) * STARBASE_FIGHTER_SCORE;
        }
        const nowDefense = baseDefense(base);
        const oldDefense = baseDefense(old);
        if (nowDefense !== null && oldDefense !== null) {
            starbaseDefenseDelta += (nowDefense - oldDefense) * STARBASE_DEFENSE_SCORE;
        }
    }

    const previousFields = new Map(
        previous.stellar_cartography
            .filter((field) => field.feature_type === "minefield")
            .map((field) => [field.feature_id, field]),
    );
    let minefieldDelta = 0;
    for (const field of current.stellar_cartography) {
        if (field.feature_type !== "minefield" || mineOwner(field) !== slotId) continue;
        const old = previousFields.get(field.feature_id);
        if (old === undefined || mineOwner(old) !== slotId) continue;
        const nowUnits = mineUnits(field);
        const oldUnits = mineUnits(old);
        if (nowUnits === null || oldUnits === null) continue;
        minefieldDelta += (nowUnits - oldUnits) * MINE_UNIT_SCORE;
    }

    const newlyObservedCombatShips = current.ships
        .filter((ship) => ship.owner_id === slotId)
        .filter((ship) => {
            const old = previousShips.get(ship.ship_id);
            return old === undefined
                || old.owner_id !== ship.owner_id
                || old.hull_id !== ship.hull_id;
        })
        .filter((ship) => hullIsCombat(ship.hull_id === null ? undefined : hulls.get(ship.hull_id)))
        .map((ship) => {
            const hull = ship.hull_id === null ? undefined : hulls.get(ship.hull_id);
            return {
                shipId: ship.ship_id,
                name: ship.name ?? `Ship #${ship.ship_id}`,
                hullId: ship.hull_id,
                hullName: recordString(hull ?? {}, "name") ?? (ship.hull_id === null ? "Unknown hull" : `Hull #${ship.hull_id}`),
                hullFloor: hullMilitaryFloor(hull),
                fighters: shipFighters(ship, hulls),
            };
        });

    const explainedDelta = mobileFighterDelta
        + starbaseFighterDelta
        + planetDefenseDelta
        + starbaseDefenseDelta
        + minefieldDelta;

    return {
        mobileFighterDelta,
        starbaseFighterDelta,
        planetDefenseDelta,
        starbaseDefenseDelta,
        minefieldDelta,
        explainedDelta,
        currentObservedMobileFighters,
        currentObservedMobileFighterScore: currentObservedMobileFighters * MOBILE_FIGHTER_SCORE,
        comparableShipFighterRecords,
        newlyObservedCombatShips,
    };
}

export function MilitaryAttributionPanel({
    game,
    history,
    linkedAccountId,
}: {
    game: GameDetailsResponse;
    history: ScoreHistoryResponse;
    linkedAccountId: number;
}) {
    const latestRows = useMemo(() => {
        const bySlot = new Map<number, ScoreHistoryItem>();
        for (const item of history.items) {
            const current = bySlot.get(item.slot_id);
            if (current === undefined || item.turn > current.turn) bySlot.set(item.slot_id, item);
        }
        return [...bySlot.values()].sort(
            (a, b) => (b.delta_military_score ?? -Infinity) - (a.delta_military_score ?? -Infinity),
        );
    }, [history.items]);

    const defaultSlot = latestRows.find((row) => (row.delta_military_score ?? 0) > 0)?.slot_id
        ?? latestRows[0]?.slot_id
        ?? null;
    const [selectedSlot, setSelectedSlot] = useState<number | null>(defaultSlot);
    const [currentIntel, setCurrentIntel] = useState<CombinedPrivateIntelResponse | null>(null);
    const [previousIntel, setPreviousIntel] = useState<CombinedPrivateIntelResponse | null>(null);
    const [catalog, setCatalog] = useState<GameRuleCatalogResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (selectedSlot === null || latestRows.some((row) => row.slot_id === selectedSlot)) return;
        setSelectedSlot(defaultSlot);
    }, [defaultSlot, latestRows, selectedSlot]);

    const score = latestRows.find((row) => row.slot_id === selectedSlot) ?? null;

    useEffect(() => {
        let cancelled = false;
        if (score === null || score.previous_turn === null) {
            setCurrentIntel(null);
            setPreviousIntel(null);
            return () => { cancelled = true; };
        }

        setLoading(true);
        setError(null);
        void Promise.all([
            getHistoricalCombinedIntel(game.game.id, linkedAccountId, score.turn),
            getHistoricalCombinedIntel(game.game.id, linkedAccountId, score.previous_turn),
            getGameRuleCatalog(game.game.id),
        ]).then(([current, previous, ruleCatalog]) => {
            if (cancelled) return;
            setCurrentIntel(current);
            setPreviousIntel(previous);
            setCatalog(ruleCatalog);
        }).catch((reason) => {
            if (!cancelled) {
                setError(reason instanceof Error ? reason.message : "Failed to attribute military score");
            }
        }).finally(() => {
            if (!cancelled) setLoading(false);
        });

        return () => { cancelled = true; };
    }, [game.game.id, linkedAccountId, score?.previous_turn, score?.turn]);

    const attribution = useMemo(() => {
        if (score === null || currentIntel === null || previousIntel === null) return null;
        return calculateAttribution(score.slot_id, currentIntel, previousIntel, catalog);
    }, [catalog, currentIntel, previousIntel, score]);

    const player = selectedSlot === null
        ? null
        : game.players.find((item) => item.slot_id === selectedSlot) ?? null;
    const publicDelta = score?.delta_military_score ?? null;
    const residual = publicDelta !== null && attribution !== null
        ? publicDelta - attribution.explainedDelta
        : null;

    return (
        <section className="panel military-attribution-panel">
            <div className="panel-header">
                <div>
                    <h2>Military Δ intelligence</h2>
                    <p>Factual lower-bound attribution. Unknown or hidden equipment is never guessed.</p>
                </div>
                <select
                    value={selectedSlot ?? ""}
                    onChange={(event) => setSelectedSlot(Number(event.target.value))}
                >
                    {latestRows.map((row) => {
                        const item = game.players.find((candidate) => candidate.slot_id === row.slot_id);
                        return (
                            <option key={row.slot_id} value={row.slot_id}>
                                {item?.username ?? `slot ${row.slot_id}`} · {formatSigned(row.delta_military_score ?? 0)}
                            </option>
                        );
                    })}
                </select>
            </div>

            {error !== null && <div className="error-box">{error}</div>}
            {loading && <p className="muted">Loading factual turn comparison…</p>}

            {!loading && score !== null && attribution !== null && (
                <>
                    <div className="military-attribution-summary">
                        <div><span>Player</span><strong>{player?.username ?? `slot ${score.slot_id}`}</strong></div>
                        <div><span>Turns</span><strong>{score.previous_turn} → {score.turn}</strong></div>
                        <div><span>Public Δ Military</span><strong>{formatSigned(publicDelta ?? 0)}</strong></div>
                        <div><span>Public Δ warships</span><strong>{formatSigned(score.delta_capital_ships ?? 0)}</strong></div>
                        <div><span>Confirmed factual Δ</span><strong>{formatSigned(attribution.explainedDelta)}</strong></div>
                        <div className={(residual ?? 0) > 5000 ? "is-warning" : ""}>
                            <span>Unattributed remainder</span>
                            <strong>{residual === null ? "—" : formatSigned(residual)}</strong>
                        </div>
                    </div>

                    <div className="military-attribution-grid">
                        <div>
                            <h3>Confirmed score changes</h3>
                            <dl>
                                <div><dt>Mobile fighters</dt><dd>{formatSigned(attribution.mobileFighterDelta)}</dd></div>
                                <div><dt>Starbase fighters</dt><dd>{formatSigned(attribution.starbaseFighterDelta)}</dd></div>
                                <div><dt>Planet defense</dt><dd>{formatSigned(attribution.planetDefenseDelta)}</dd></div>
                                <div><dt>Starbase defense</dt><dd>{formatSigned(attribution.starbaseDefenseDelta)}</dd></div>
                                <div><dt>Minefields</dt><dd>{formatSigned(attribution.minefieldDelta)}</dd></div>
                            </dl>
                            <p className="muted">
                                {attribution.comparableShipFighterRecords} ship fighter records were directly comparable across both turns.
                            </p>
                        </div>

                        <div>
                            <h3>Observed fighter stock</h3>
                            <strong className="military-big-number">
                                {attribution.currentObservedMobileFighters.toLocaleString()} fighters
                            </strong>
                            <p>
                                At least {formatScore(attribution.currentObservedMobileFighterScore)} Military is currently visible in mobile fighters alone.
                            </p>
                            <p className="muted">This is current stock, not necessarily this turn's increase.</p>
                        </div>
                    </div>

                    <div className="military-new-ships">
                        <h3>Newly observed combat hulls this turn</h3>
                        {attribution.newlyObservedCombatShips.length === 0 ? (
                            <p className="muted">None in accessible factual snapshots.</p>
                        ) : (
                            attribution.newlyObservedCombatShips.map((ship) => (
                                <div key={ship.shipId} className="military-new-ship-row">
                                    <div>
                                        <strong>#{ship.shipId} {ship.name}</strong>
                                        <small>{ship.hullName}</small>
                                    </div>
                                    <div>
                                        <span>Hull-only floor</span>
                                        <strong>{ship.hullFloor === null ? "—" : formatScore(ship.hullFloor)}</strong>
                                    </div>
                                    <div>
                                        <span>Observed fighters</span>
                                        <strong>{ship.fighters ?? "—"}</strong>
                                    </div>
                                </div>
                            ))
                        )}
                        <p className="muted">
                            Newly observed does not prove newly built. Hull-only floor excludes engines, beams, launchers and loaded ammunition.
                        </p>
                    </div>

                    {residual !== null && residual > 5000 && (
                        <div className="military-attribution-warning">
                            <strong>Large unexplained military increase</strong>
                            <p>
                                {formatScore(residual)} points remain after directly comparable fighters, defenses and minefields. Plausible sources include new or previously hidden warships and their equipment, unobserved fighter loading, or military assets outside current intel coverage.
                            </p>
                        </div>
                    )}
                </>
            )}
        </section>
    );
}
