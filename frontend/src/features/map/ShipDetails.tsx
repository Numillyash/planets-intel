import type { PlayerInfo } from "../../types/api";
import type {
    MapShipObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
import { SHIP_ROLE_LABEL, shipRole, type SelectedEntity } from "./mapModel";
import { formatInteger, formatPercent, shipFacts } from "./observationView";
import { DetailSection, FactRow, playerName } from "./DetailPrimitives";

export function ShipDetails({
    ship,
    intel,
    players,
    onSelect,
}: {
    ship: MapShipObservation;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    const role = shipRole(ship);
    const facts = shipFacts(ship);
    const orbitPlanet = intel.planets.find(
        (planet) =>
            planet.x !== null &&
            planet.y !== null &&
            ship.x === planet.x &&
            ship.y === planet.y,
    ) ?? null;

    const showBeams = role !== "freighter" && facts.beams !== null && facts.beams > 0;
    const showTubes = (role === "torpedo" || role === "warship") && facts.tubes !== null && facts.tubes > 0;
    const showBays = (role === "carrier" || role === "warship") && facts.bays !== null && facts.bays > 0;
    const hasArmament = showBeams || showTubes || showBays;

    const showTorpedoes = showTubes && facts.torpedoes !== null;
    const showFighters = showBays && facts.fighters !== null;

    return (
        <div className="intel-entity-details">
            <span className="intel-entity-kind">Ship</span>
            <h3>{ship.name ?? `Ship ${ship.ship_id}`}</h3>
            <div className="intel-detail-badges">
                <span className="intel-detail-badge">{SHIP_ROLE_LABEL[role]}</span>
                {orbitPlanet !== null && (
                    <button
                        className="intel-detail-badge intel-detail-badge-button"
                        onClick={() => onSelect({ kind: "planet", value: orbitPlanet })}
                        type="button"
                    >
                        Orbiting {orbitPlanet.name ?? `#${orbitPlanet.planet_id}`}
                    </button>
                )}
            </div>

            <DetailSection title="Ship status">
                <dl className="intel-fact-list">
                    <FactRow label="ID" value={ship.ship_id} />
                    <FactRow label="Owner" value={playerName(ship.owner_id, players)} />
                    <FactRow label="Hull" value={facts.hullName ?? `Hull #${ship.hull_id ?? "—"}`} />
                    <FactRow label="Engine" value={facts.engineName ?? (facts.engineId !== null ? `Engine #${facts.engineId}` : "—")} />
                    <FactRow label="Damage" value={formatPercent(facts.damage)} />
                    <FactRow label="Crew" value={formatInteger(facts.crew)} />
                    <FactRow label="Info turn" value={ship.info_turn ?? "—"} />
                </dl>
            </DetailSection>

            {hasArmament && (
                <DetailSection title="Armament">
                    <dl className="intel-fact-list">
                        {showBeams && <FactRow label="Beams" value={facts.beams ?? "—"} />}
                        {showTubes && <FactRow label="Tubes" value={facts.tubes ?? "—"} />}
                        {showBays && <FactRow label="Fighter bays" value={facts.bays ?? "—"} />}
                        {showTorpedoes && <FactRow label="Torpedoes" value={formatInteger(facts.torpedoes)} />}
                        {showFighters && <FactRow label="Fighters" value={formatInteger(facts.fighters)} />}
                    </dl>
                </DetailSection>
            )}

            <DetailSection title="Cargo">
                <div className="intel-cargo-grid">
                    <div><span>Fuel</span><strong>{formatInteger(facts.fuel)}</strong></div>
                    <div><span>Clans</span><strong>{formatInteger(facts.clans)}</strong></div>
                    <div><span>Supplies</span><strong>{formatInteger(facts.supplies)}</strong></div>
                    <div><span>MegaCredits</span><strong>{formatInteger(facts.megacredits)}</strong></div>
                    <div><span>Duranium</span><strong>{formatInteger(facts.duranium)}</strong></div>
                    <div><span>Tritanium</span><strong>{formatInteger(facts.tritanium)}</strong></div>
                    <div><span>Molybdenum</span><strong>{formatInteger(facts.molybdenum)}</strong></div>
                </div>
            </DetailSection>

            <DetailSection title="Movement">
                <dl className="intel-fact-list">
                    <FactRow label="Position" value={
                        ship.x !== null && ship.y !== null
                            ? `${ship.x}, ${ship.y}`
                            : "—"
                    } />
                    <FactRow label="Warp" value={ship.warp ?? "—"} />
                    <FactRow label="Waypoint" value={
                        facts.waypointX !== null && facts.waypointY !== null
                            ? `${facts.waypointX}, ${facts.waypointY}`
                            : "—"
                    } />
                    <FactRow label="Mission" value={facts.mission ?? "—"} />
                </dl>
            </DetailSection>
        </div>
    );
}
