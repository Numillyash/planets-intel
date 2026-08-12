import type { PlayerInfo } from "../../types/api";
import type {
    MapPlanetObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import { SHIP_ROLE_LABEL, shipRole, shipsAtPlanet } from "./mapModel";
import { formatInteger, formatPercent, formatTemperature, planetFacts } from "./observationView";
import { DetailSection, FactRow, MineralRow, playerName } from "./DetailPrimitives";

export function PlanetDetails({
    planet,
    intel,
    players,
    onSelect,
}: {
    planet: MapPlanetObservation;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    const facts = planetFacts(planet);
    const starbase = intel.starbases.find(
        (item) => item.planet_id === planet.planet_id,
    ) ?? null;
    const orbitShips = shipsAtPlanet(intel.ships, planet);
    const hasResources = [
        facts.supplies,
        facts.megacredits,
        facts.neutronium.surface,
        facts.neutronium.ground,
        facts.neutronium.density,
        facts.duranium.surface,
        facts.duranium.ground,
        facts.duranium.density,
        facts.tritanium.surface,
        facts.tritanium.ground,
        facts.tritanium.density,
        facts.molybdenum.surface,
        facts.molybdenum.ground,
        facts.molybdenum.density,
    ].some((value) => value !== null);
    const hasColony = [
        facts.clans,
        facts.colonistHappiness,
        facts.colonistTaxRate,
        facts.nativeRace,
        facts.nativeClans,
        facts.nativeGovernment,
        facts.nativeHappiness,
        facts.nativeTaxRate,
    ].some((value) => value !== null);

    return (
        <div className="intel-entity-details intel-planet-details">
            <span className="intel-entity-kind">Planet</span>
            <h3>{planet.name ?? `Planet ${planet.planet_id}`}</h3>

            <div className="intel-detail-badges">
                <span className="intel-detail-badge">
                    {facts.knownFieldCount > 0 ? "Detailed scan" : "Position only"}
                </span>
                {starbase !== null && (
                    <span className="intel-detail-badge intel-detail-badge-gold">
                        Starbase
                    </span>
                )}
                {orbitShips.length > 0 && (
                    <span className="intel-detail-badge">
                        {orbitShips.length} ship{orbitShips.length === 1 ? "" : "s"} in orbit
                    </span>
                )}
            </div>

            <dl className="intel-fact-list intel-fact-list-summary">
                <FactRow label="ID" value={planet.planet_id} />
                <FactRow label="Owner" value={playerName(planet.owner_id, players)} />
                <FactRow label="Info turn" value={planet.info_turn ?? "—"} />
                <FactRow label="Position" value={
                    planet.x !== null && planet.y !== null
                        ? `${planet.x}, ${planet.y}`
                        : "—"
                } />
                <FactRow label="Temperature" value={formatTemperature(facts.temperature)} />
            </dl>

            <DetailSection title="Buildings">
                <dl className="intel-fact-list">
                    <FactRow label="Mines" value={formatInteger(facts.mines)} />
                    <FactRow label="Factories" value={formatInteger(facts.factories)} />
                    <FactRow label="Defense posts" value={formatInteger(facts.defense)} />
                </dl>
            </DetailSection>

            <DetailSection title="Resources">
                {hasResources ? (
                    <>
                        <div className="intel-resource-summary">
                            <div>
                                <span>Supplies</span>
                                <strong>{formatInteger(facts.supplies)}</strong>
                            </div>
                            <div>
                                <span>MegaCredits</span>
                                <strong>{formatInteger(facts.megacredits)}</strong>
                            </div>
                        </div>
                        <div className="intel-mineral-table-wrap">
                            <table className="intel-mineral-table">
                                <thead>
                                    <tr>
                                        <th>Mineral</th>
                                        <th>Surface</th>
                                        <th>Ground</th>
                                        <th>Density</th>
                                        <th>Prod.</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <MineralRow label="Neutronium" facts={facts.neutronium} />
                                    <MineralRow label="Duranium" facts={facts.duranium} />
                                    <MineralRow label="Tritanium" facts={facts.tritanium} />
                                    <MineralRow label="Molybdenum" facts={facts.molybdenum} />
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    <p className="intel-no-facts">
                        This factual observation does not contain detailed resource data.
                    </p>
                )}
            </DetailSection>

            <DetailSection title="Colony">
                {hasColony ? (
                    <div className="intel-colony-grid">
                        <div className="intel-colony-card">
                            <span>Colonists</span>
                            <strong>{formatInteger(facts.clans)} clans</strong>
                            <small>
                                Happiness {formatInteger(facts.colonistHappiness)} · Tax {formatPercent(facts.colonistTaxRate)}
                            </small>
                        </div>
                        <div className="intel-colony-card">
                            <span>Natives</span>
                            <strong>{facts.nativeRace ?? "None / unknown"}</strong>
                            <small>{formatInteger(facts.nativeClans)} clans</small>
                            <small>{facts.nativeGovernment ?? "Government unknown"}</small>
                            <small>
                                Happiness {formatInteger(facts.nativeHappiness)} · Tax {formatPercent(facts.nativeTaxRate)}
                            </small>
                        </div>
                    </div>
                ) : (
                    <p className="intel-no-facts">
                        No colony or native population facts are present in this observation.
                    </p>
                )}
            </DetailSection>

            {(starbase !== null || orbitShips.length > 0) && (
                <DetailSection title="Orbit">
                    <div className="intel-orbit-list">
                        {starbase !== null && (
                            <button
                                className="intel-orbit-item"
                                onClick={() => onSelect({ kind: "starbase", value: starbase })}
                                type="button"
                            >
                                <span className="intel-orbit-symbol intel-orbit-symbol-base" />
                                <span>
                                    <strong>Starbase #{starbase.starbase_id}</strong>
                                    <small>Open factual starbase observation</small>
                                </span>
                            </button>
                        )}
                        {orbitShips.map((ship) => (
                            <button
                                className="intel-orbit-item"
                                key={ship.ship_id}
                                onClick={() => onSelect({ kind: "ship", value: ship })}
                                type="button"
                            >
                                <span className={`intel-orbit-symbol intel-orbit-symbol-${shipRole(ship)}`} />
                                <span>
                                    <strong>{ship.name ?? `Ship ${ship.ship_id}`}</strong>
                                    <small>{SHIP_ROLE_LABEL[shipRole(ship)]} · ID {ship.ship_id}</small>
                                </span>
                            </button>
                        ))}
                    </div>
                </DetailSection>
            )}
        </div>
    );
}
