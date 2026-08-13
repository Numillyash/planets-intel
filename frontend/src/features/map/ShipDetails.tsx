import type { PlayerInfo } from "../../types/api";
import {
    isCombinedPrivateIntel,
    type MapShipObservation,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { SHIP_ROLE_LABEL, shipRole, type SelectedEntity } from "./mapModel";
import {
    analyzeRouteRadiation,
    ionStormAtPoint,
    routeDistance,
    shipHistoryRoute,
    shipOwnerRaceId,
    shipPlannedRoute,
} from "./navigationAnalysis";
import {
    factNumber,
    formatInteger,
    formatPercent,
    shipFacts,
} from "./observationView";
import { DetailSection, FactRow, playerName } from "./DetailPrimitives";
import { ThreatAnalysis } from "./ThreatAnalysis";


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

    const plannedRoute = shipPlannedRoute(ship);
    const historyRoute = shipHistoryRoute(ship);
    const radiation = analyzeRouteRadiation(intel, plannedRoute);
    const ownerRaceId = shipOwnerRaceId(ship, players);
    const robotImmune = ownerRaceId === 9;
    const isCloaked = ship.payload.iscloaked === true;
    const nominalRadiationLoss = robotImmune ? 0 : radiation.maxRadiation;
    const crewAfterRadiation = (
        !radiation.coreCrossing && facts.crew !== null
            ? Math.max(facts.crew - nominalRadiationLoss, 0)
            : null
    );
    const clansAfterRadiation = (
        !radiation.coreCrossing && facts.clans !== null
            ? Math.max(facts.clans - nominalRadiationLoss, 0)
            : null
    );
    const radiationClusterName = radiation.cluster?.name
        ?? (radiation.cluster !== null
            ? `Star cluster #${radiation.cluster.feature_id}`
            : null);

    const ionHazard = (
        ship.x !== null && ship.y !== null
            ? ionStormAtPoint(intel, ship.x, ship.y)
            : null
    );
    const shipMass = factNumber(ship.payload, "mass");
    const normalIonDragApplies = (
        ionHazard !== null &&
        ionHazard.stormClass >= 4 &&
        (shipMass === null || shipMass <= 4000)
    );
    const linkedAccountId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;

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
                {ionHazard?.randomTransportRisk && (
                    <span className="intel-detail-badge intel-detail-badge-gold">
                        Ion transport risk
                    </span>
                )}
            </div>

            <DetailSection title="Ship status">
                <dl className="intel-fact-list">
                    <FactRow label="ID" value={ship.ship_id} />
                    <FactRow label="Owner" value={playerName(ship.owner_id, players)} />
                    <FactRow label="Friendly code" value={facts.friendlyCode ?? "—"} />
                    <FactRow label="Hull" value={facts.hullName ?? `Hull #${ship.hull_id ?? "—"}`} />
                    <FactRow label="Engine" value={facts.engineName ?? (facts.engineId !== null ? `Engine #${facts.engineId}` : "—")} />
                    <FactRow label="Mass" value={shipMass !== null ? `${Math.round(shipMass)} kt` : "—"} />
                    <FactRow label="Damage" value={formatPercent(facts.damage)} />
                    <FactRow label="Crew" value={formatInteger(facts.crew)} />
                    <FactRow label="Info turn" value={ship.info_turn ?? "—"} />
                </dl>
            </DetailSection>

            <ThreatAnalysis
                gameId={intel.game_id}
                linkedAccountId={linkedAccountId}
                shipId={ship.ship_id}
                turn={intel.turn}
            />

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

            <DetailSection title="Movement & trajectory">
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
                    <FactRow label="Route" value={
                        plannedRoute.length >= 2
                            ? `${routeDistance(plannedRoute).toFixed(1)} ly · ${plannedRoute.length - 1} leg${plannedRoute.length === 2 ? "" : "s"}`
                            : "No movement orders observed"
                    } />
                    <FactRow label="Payload history" value={
                        historyRoute.length >= 2
                            ? `${historyRoute.length} observed points`
                            : "—"
                    } />
                    <FactRow label="Mission" value={facts.mission ?? "—"} />
                </dl>
                <p className="intel-no-facts" style={{ marginTop: 8 }}>
                    Cyan line = observed movement orders. Factual multi-turn tracks are reconstructed separately from stored turn snapshots and are drawn behind the current map.
                </p>
            </DetailSection>

            <DetailSection title="Star-cluster radiation">
                {radiation.coreCrossing ? (
                    <p className="intel-no-facts" style={{ color: "#ff7c8d" }}>
                        Planned trajectory intersects a star-cluster core. A ship crossing the core is destroyed.
                    </p>
                ) : (
                    <dl className="intel-fact-list">
                        <FactRow label="Max radiation" value={radiation.maxRadiation} />
                        <FactRow label="Cluster" value={radiationClusterName ?? "None on route"} />
                        <FactRow label="Crew loss" value={robotImmune ? "0 (Robots immune)" : nominalRadiationLoss} />
                        <FactRow label="Crew after" value={crewAfterRadiation !== null ? crewAfterRadiation : "—"} />
                        <FactRow label="Clans after" value={clansAfterRadiation !== null ? clansAfterRadiation : "—"} />
                        {isCloaked && radiation.maxRadiation > 0 && !robotImmune && (
                            <FactRow label="If cloak holds" value={`normal ≈ ${Math.ceil(radiation.maxRadiation / 2)}, advanced ≈ ${Math.ceil(radiation.maxRadiation / 3)}`} />
                        )}
                    </dl>
                )}
                <p className="intel-no-facts" style={{ marginTop: 8 }}>
                    Loss uses the maximum star-cluster radiation crossed by the observed route. Hull-specific radiation shielding and protection while docked at an appropriate friendly starbase are not yet imported into this estimate.
                </p>
            </DetailSection>

            {ionHazard !== null && (
                <DetailSection title="Ion storm hazard">
                    <dl className="intel-fact-list">
                        <FactRow label="Local voltage" value={`${Math.round(ionHazard.localVoltage)} meV`} />
                        <FactRow label="Class" value={ionHazard.stormClass} />
                        <FactRow label="Storm warp" value={ionHazard.warp ?? "—"} />
                        <FactRow label="Heading" value={ionHazard.heading ?? "—"} />
                        <FactRow
                            label="Drag"
                            value={
                                normalIonDragApplies && ionHazard.dragDistance !== null
                                    ? `≈ ${ionHazard.dragDistance.toFixed(1)} ly before own vector`
                                    : ionHazard.stormClass >= 4
                                        ? "Class 4/5; mass/advanced-cloak effects may alter drag"
                                        : "No Class-4 drag"
                            }
                        />
                        <FactRow
                            label="Transport"
                            value={
                                ionHazard.extremeTransportRisk
                                    ? "EXTREME: disappearance/destruction reports above ~451 meV"
                                    : ionHazard.randomTransportRisk
                                        ? "Random long-range transport possible above ~400 meV"
                                        : "No >400 meV transport warning"
                            }
                        />
                    </dl>
                    <p className="intel-no-facts" style={{ marginTop: 8 }}>
                        Ion-storm crew damage is not included in the numeric star-cluster loss estimate: the official rules make it depend on ship mass, storm voltage and crew experience, without publishing a complete deterministic formula.
                    </p>
                </DetailSection>
            )}
        </div>
    );
}
