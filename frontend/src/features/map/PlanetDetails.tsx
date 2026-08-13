import { useEffect, useState } from "react";
import { getHistoricalShipTracks } from "../../api/history";
import type { PlayerInfo } from "../../types/api";
import {
    isCombinedPrivateIntel,
    type MapPlanetObservation,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import type {
    HistoricalShipTrack,
    HistoricalShipTrackPoint,
} from "../../types/history";
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

    const linkedAccountId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;

    const directShipIds = new Set(
        orbitShips.map((ship) => ship.ship_id),
    );
    const directShipKey = [...directShipIds]
        .sort((left, right) => left - right)
        .join(",");

    const [combatOrbitContacts, setCombatOrbitContacts] = useState<
        Array<{
            track: HistoricalShipTrack;
            point: HistoricalShipTrackPoint;
        }>
    >([]);

    useEffect(() => {
        let active = true;

        void getHistoricalShipTracks(
            intel.game_id,
            linkedAccountId,
            intel.turn,
        )
            .then((data) => {
                if (!active) return;

                const contacts: Array<{
                    track: HistoricalShipTrack;
                    point: HistoricalShipTrackPoint;
                }> = [];

                for (const track of data.tracks) {
                    // A normal current ShipObservation already has its own
                    // orbit entry. Do not duplicate it.
                    if (directShipIds.has(track.ship_id)) {
                        continue;
                    }

                    const point = track.points.find(
                        (item) =>
                            item.turn === intel.turn &&
                            item.post_host_confirmed &&
                            item.post_host_planet_id === planet.planet_id,
                    );

                    if (point !== undefined) {
                        contacts.push({ track, point });
                    }
                }

                contacts.sort(
                    (left, right) =>
                        left.track.ship_id - right.track.ship_id,
                );

                setCombatOrbitContacts(contacts);
            })
            .catch(() => {
                if (active) {
                    setCombatOrbitContacts([]);
                }
            });

        return () => {
            active = false;
        };
    }, [
        directShipKey,
        intel.game_id,
        intel.turn,
        linkedAccountId,
        planet.planet_id,
    ]);

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
                        {orbitShips.length} directly observed ship
                        {orbitShips.length === 1 ? "" : "s"} in orbit
                    </span>
                )}
                {combatOrbitContacts.length > 0 && (
                    <span
                        className="intel-detail-badge intel-detail-badge-gold"
                        title="Ship presence is confirmed by VCR and post-host Fleet Command evidence"
                    >
                        {combatOrbitContacts.length} combat-confirmed ship
                        {combatOrbitContacts.length === 1 ? "" : "s"} in orbit
                    </span>
                )}
            </div>

            <dl className="intel-fact-list intel-fact-list-summary">
                <FactRow label="ID" value={planet.planet_id} />
                <FactRow label="Owner" value={playerName(planet.owner_id, players)} />
                <FactRow label="Friendly code" value={facts.friendlyCode ?? "—"} />
                <FactRow label="Info turn" value={planet.info_turn ?? "—"} />
                <FactRow label="Position" value={
                    planet.x !== null && planet.y !== null
                        ? `${planet.x}, ${planet.y}`
                        : "—"
                } />
                <FactRow label="Temperature" value={formatTemperature(facts.temperature)} />
            </dl>

            {(starbase !== null ||
                orbitShips.length > 0 ||
                combatOrbitContacts.length > 0) && (
                <DetailSection title="Ships in orbit">
                    <div className="intel-orbit-list">
                        {starbase !== null && (
                            <button
                                className="intel-orbit-item"
                                onClick={() =>
                                    onSelect({
                                        kind: "starbase",
                                        value: starbase,
                                    })
                                }
                                type="button"
                            >
                                <span className="intel-orbit-symbol intel-orbit-symbol-base" />
                                <span>
                                    <strong>
                                        Starbase #{starbase.starbase_id}
                                    </strong>
                                    <small>
                                        Open factual starbase observation
                                    </small>
                                </span>
                            </button>
                        )}

                        {orbitShips.map((ship) => (
                            <button
                                className="intel-orbit-item"
                                key={`scan:${ship.ship_id}`}
                                onClick={() =>
                                    onSelect({
                                        kind: "ship",
                                        value: ship,
                                    })
                                }
                                type="button"
                            >
                                <span
                                    className={
                                        `intel-orbit-symbol intel-orbit-symbol-${shipRole(ship)}`
                                    }
                                />
                                <span>
                                    <strong>
                                        {ship.name ?? `Ship ${ship.ship_id}`}
                                    </strong>
                                    <small>
                                        {SHIP_ROLE_LABEL[shipRole(ship)]}
                                        {" · "}ID {ship.ship_id}
                                        {" · "}direct observation
                                    </small>
                                </span>
                            </button>
                        ))}

                        {combatOrbitContacts.map(({ track, point }) => (
                            <button
                                className="intel-orbit-item"
                                key={`combat:${track.ship_id}:${point.turn}`}
                                onClick={() => {
                                    const event = point.combat_event;
                                    if (event === null) return;

                                    window.dispatchEvent(
                                        new CustomEvent(
                                            "dashboard-event-select",
                                            {
                                                detail: {
                                                    turn: event.turn,
                                                    vcrId: event.vcr_id,
                                                },
                                            },
                                        ),
                                    );
                                }}
                                type="button"
                                title="Open VCR / combat evidence"
                            >
                                <span
                                    className="intel-orbit-symbol"
                                    style={{
                                        background: "#244f3a",
                                        borderColor: "#82e6b1",
                                    }}
                                />
                                <span>
                                    <strong>
                                        {track.name ?? `Ship ${track.ship_id}`}
                                        {" · "}#{track.ship_id}
                                    </strong>
                                    <small style={{ color: "#82e6b1" }}>
                                        Combat-confirmed in orbit after host
                                        {" · "}Fleet Command
                                        {" · "}T{point.turn}
                                    </small>
                                </span>
                            </button>
                        ))}
                    </div>
                </DetailSection>
            )}

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
                            <div><span>Supplies</span><strong>{formatInteger(facts.supplies)}</strong></div>
                            <div><span>MegaCredits</span><strong>{formatInteger(facts.megacredits)}</strong></div>
                        </div>
                        <div className="intel-mineral-table-wrap">
                            <table className="intel-mineral-table">
                                <thead><tr><th>Mineral</th><th>Surface</th><th>Ground</th><th>Density</th><th>Prod.</th></tr></thead>
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
                    <p className="intel-no-facts">This factual observation does not contain detailed resource data.</p>
                )}
            </DetailSection>

            <DetailSection title="Colony">
                {hasColony ? (
                    <div className="intel-colony-grid">
                        <div className="intel-colony-card">
                            <span>Colonists</span>
                            <strong>{formatInteger(facts.clans)} clans</strong>
                            <small>Happiness {formatInteger(facts.colonistHappiness)} · Tax {formatPercent(facts.colonistTaxRate)}</small>
                        </div>
                        <div className="intel-colony-card">
                            <span>Natives</span>
                            <strong>{facts.nativeRace ?? "None / unknown"}</strong>
                            <small>{formatInteger(facts.nativeClans)} clans</small>
                            <small>{facts.nativeGovernment ?? "Government unknown"}</small>
                            <small>Happiness {formatInteger(facts.nativeHappiness)} · Tax {formatPercent(facts.nativeTaxRate)}</small>
                        </div>
                    </div>
                ) : (
                    <p className="intel-no-facts">No colony or native population facts are present in this observation.</p>
                )}
            </DetailSection>

        </div>
    );
}
