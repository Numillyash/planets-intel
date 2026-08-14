import { useEffect, useMemo, useState } from "react";

import { getHistoricalShipTracks } from "../../api/history";
import type { PlayerInfo } from "../../types/api";
import type {
    HistoricalShipTrack,
    HistoricalShipTrackPoint,
} from "../../types/history";
import {
    isCombinedPrivateIntel,
    type MapPlanetObservation,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { DetailSection, FactRow, MineralRow, playerName } from "./DetailPrimitives";
import type { SelectedEntity } from "./mapModel";
import { SHIP_ROLE_LABEL, shipRole, shipsAtPlanet } from "./mapModel";
import {
    formatInteger,
    formatPercent,
    formatTemperature,
    planetFacts,
} from "./observationView";
import type { PlanetPostHostState } from "./planetPostHostState";

export type PlanetOperationalTab =
    | "planet"
    | "economy"
    | "ships"
    | "intel"
    | "history"
    | "combat";

interface CombatOrbitContact {
    track: HistoricalShipTrack;
    point: HistoricalShipTrackPoint;
}

function openCombatEvent(point: HistoricalShipTrackPoint) {
    const event = point.combat_event;
    if (event === null) return;

    window.dispatchEvent(
        new CustomEvent("dashboard-event-select", {
            detail: {
                turn: event.turn,
                vcrId: event.vcr_id,
            },
        }),
    );
}

function EvidenceLine({ contact }: { contact: CombatOrbitContact }) {
    const { track, point } = contact;
    return (
        <button
            className="intel-orbit-item operational-evidence-item"
            onClick={() => openCombatEvent(point)}
            type="button"
            title="Open VCR / combat evidence"
        >
            <span className="intel-orbit-symbol operational-evidence-symbol" />
            <span>
                <strong>
                    {track.name ?? `Ship ${track.ship_id}`} · #{track.ship_id}
                </strong>
                <small>
                    Combat-confirmed after host · Fleet Command · T{point.turn}
                    {point.combat_vcr_id !== null ? ` · VCR #${point.combat_vcr_id}` : ""}
                </small>
            </span>
        </button>
    );
}

export function OperationalPlanetPanel({
    tab,
    planet,
    intel,
    players,
    postHostState,
    onSelect,
}: {
    tab: PlanetOperationalTab;
    planet: MapPlanetObservation;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    postHostState: PlanetPostHostState | null;
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
    const effectiveOwnerId = postHostState?.ownerId ?? planet.owner_id;
    const ownerChanged =
        postHostState !== null &&
        postHostState.ownerId !== planet.owner_id;

    const directShipIds = useMemo(
        () => new Set(orbitShips.map((ship) => ship.ship_id)),
        [orbitShips],
    );
    const directShipKey = useMemo(
        () => [...directShipIds].sort((left, right) => left - right).join(","),
        [directShipIds],
    );

    const [combatOrbitContacts, setCombatOrbitContacts] = useState<CombatOrbitContact[]>([]);
    const [tracksLoading, setTracksLoading] = useState(false);

    useEffect(() => {
        let active = true;
        setTracksLoading(true);

        void getHistoricalShipTracks(
            intel.game_id,
            linkedAccountId,
            intel.turn,
        )
            .then((data) => {
                if (!active) return;

                const contacts: CombatOrbitContact[] = [];
                for (const track of data.tracks) {
                    if (directShipIds.has(track.ship_id)) continue;

                    const point = track.points.find(
                        (item) =>
                            item.turn === intel.turn &&
                            item.post_host_confirmed &&
                            item.post_host_planet_id === planet.planet_id,
                    );
                    if (point !== undefined) contacts.push({ track, point });
                }

                contacts.sort(
                    (left, right) => left.track.ship_id - right.track.ship_id,
                );
                setCombatOrbitContacts(contacts);
            })
            .catch(() => {
                if (active) setCombatOrbitContacts([]);
            })
            .finally(() => {
                if (active) setTracksLoading(false);
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

    if (tab === "planet") {
        return (
            <div className="operational-tab-section">
                <div className="intel-detail-badges">
                    <span className="intel-detail-badge">
                        {facts.knownFieldCount > 0 ? "Detailed scan" : "Position only"}
                    </span>
                    {ownerChanged && (
                        <span className="intel-detail-badge operational-owner-change-badge">
                            Owner changed after host
                        </span>
                    )}
                    {starbase !== null && (
                        <span className="intel-detail-badge intel-detail-badge-gold">Starbase</span>
                    )}
                    {orbitShips.length > 0 && (
                        <span className="intel-detail-badge">
                            {orbitShips.length} scanned ship{orbitShips.length === 1 ? "" : "s"} in orbit
                        </span>
                    )}
                    {combatOrbitContacts.length > 0 && (
                        <span className="intel-detail-badge intel-detail-badge-gold">
                            {combatOrbitContacts.length} combat-confirmed ship{combatOrbitContacts.length === 1 ? "" : "s"}
                        </span>
                    )}
                </div>

                <dl className="intel-fact-list intel-fact-list-summary">
                    <FactRow label="Planet ID" value={planet.planet_id} />
                    <FactRow label="Owner" value={playerName(effectiveOwnerId, players)} />
                    {ownerChanged && (
                        <FactRow
                            label="Snapshot owner"
                            value={playerName(planet.owner_id, players)}
                        />
                    )}
                    <FactRow label="Friendly code" value={facts.friendlyCode ?? "—"} />
                    <FactRow label="Info turn" value={planet.info_turn ?? "—"} />
                    <FactRow
                        label="Position"
                        value={
                            planet.x !== null && planet.y !== null
                                ? `${planet.x}, ${planet.y}`
                                : "—"
                        }
                    />
                    <FactRow label="Temperature" value={formatTemperature(facts.temperature)} />
                </dl>

                {ownerChanged && postHostState !== null && (
                    <div className="operational-intel-callout operational-owner-change-callout">
                        <strong>Post-host factual state</strong>
                        <span>
                            Fleet/host evidence confirms {playerName(postHostState.ownerId, players)}
                            {" "}as owner after VCR #{postHostState.vcrId} on turn {postHostState.turn}.
                            The stored planet snapshot above is retained separately for provenance.
                        </span>
                    </div>
                )}

                <DetailSection title="Population">
                    <div className="operational-summary-grid">
                        <div>
                            <span>Colonists</span>
                            <strong>{formatInteger(facts.clans)}</strong>
                        </div>
                        <div>
                            <span>Natives</span>
                            <strong>{facts.nativeRace ?? "—"}</strong>
                        </div>
                        <div>
                            <span>Native clans</span>
                            <strong>{formatInteger(facts.nativeClans)}</strong>
                        </div>
                        <div>
                            <span>Native gov.</span>
                            <strong>{facts.nativeGovernment ?? "—"}</strong>
                        </div>
                    </div>
                </DetailSection>

                <DetailSection title="Structures">
                    <div className="operational-summary-grid">
                        <div>
                            <span>Mines</span>
                            <strong>{formatInteger(facts.mines)}</strong>
                        </div>
                        <div>
                            <span>Factories</span>
                            <strong>{formatInteger(facts.factories)}</strong>
                        </div>
                        <div>
                            <span>Defense</span>
                            <strong>{formatInteger(facts.defense)}</strong>
                        </div>
                        <div>
                            <span>Starbase</span>
                            <strong>{starbase !== null ? "Yes" : "No"}</strong>
                        </div>
                    </div>
                </DetailSection>

                <DetailSection title="Planet cargo">
                    <div className="operational-summary-grid operational-resource-grid">
                        <div>
                            <span>Neutronium</span>
                            <strong>{formatInteger(facts.neutronium.surface)}</strong>
                        </div>
                        <div>
                            <span>Duranium</span>
                            <strong>{formatInteger(facts.duranium.surface)}</strong>
                        </div>
                        <div>
                            <span>Tritanium</span>
                            <strong>{formatInteger(facts.tritanium.surface)}</strong>
                        </div>
                        <div>
                            <span>Molybdenum</span>
                            <strong>{formatInteger(facts.molybdenum.surface)}</strong>
                        </div>
                        <div>
                            <span>Supplies</span>
                            <strong>{formatInteger(facts.supplies)}</strong>
                        </div>
                        <div>
                            <span>MegaCredits</span>
                            <strong>{formatInteger(facts.megacredits)}</strong>
                        </div>
                    </div>
                </DetailSection>
            </div>
        );
    }

    if (tab === "economy") {
        return (
            <div className="operational-tab-section">
                <DetailSection title="Infrastructure">
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
                                    <thead>
                                        <tr><th>Mineral</th><th>Surface</th><th>Ground</th><th>Density</th><th>Prod.</th></tr>
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
                        <p className="intel-no-facts">No detailed resource scan is present.</p>
                    )}
                </DetailSection>

                <DetailSection title="Population & taxation">
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
                        <p className="intel-no-facts">No colony or native population facts are present.</p>
                    )}
                </DetailSection>
            </div>
        );
    }

    if (tab === "ships") {
        return (
            <div className="operational-tab-section">
                <div className="operational-section-heading">
                    <span>Orbit</span>
                    <strong>
                        {orbitShips.length + combatOrbitContacts.length} ship
                        {orbitShips.length + combatOrbitContacts.length === 1 ? "" : "s"}
                    </strong>
                </div>
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
                                <small>Open starbase interface</small>
                            </span>
                        </button>
                    )}
                    {orbitShips.map((ship) => (
                        <button
                            className="intel-orbit-item"
                            key={`scan:${ship.ship_id}`}
                            onClick={() => onSelect({ kind: "ship", value: ship })}
                            type="button"
                        >
                            <span className={`intel-orbit-symbol intel-orbit-symbol-${shipRole(ship)}`} />
                            <span>
                                <strong>{ship.name ?? `Ship ${ship.ship_id}`}</strong>
                                <small>
                                    {SHIP_ROLE_LABEL[shipRole(ship)]} · ID {ship.ship_id} · direct observation
                                </small>
                            </span>
                        </button>
                    ))}
                    {combatOrbitContacts.map((contact) => (
                        <EvidenceLine
                            contact={contact}
                            key={`combat:${contact.track.ship_id}:${contact.point.turn}`}
                        />
                    ))}
                    {!tracksLoading && starbase === null && orbitShips.length === 0 && combatOrbitContacts.length === 0 && (
                        <p className="intel-no-facts">No ships or starbase are currently known in orbit.</p>
                    )}
                </div>
            </div>
        );
    }

    if (tab === "intel") {
        return (
            <div className="operational-tab-section">
                <div className="operational-intel-callout">
                    <strong>Intel overlay</strong>
                    <span>
                        Factual snapshot values remain separate from combat-derived and host-confirmed evidence.
                    </span>
                </div>
                <dl className="intel-fact-list">
                    <FactRow label="Effective owner" value={playerName(effectiveOwnerId, players)} />
                    {ownerChanged && (
                        <FactRow label="Snapshot owner" value={playerName(planet.owner_id, players)} />
                    )}
                    <FactRow label="Snapshot turn" value={intel.turn} />
                    <FactRow label="Planet info turn" value={planet.info_turn ?? "—"} />
                    <FactRow label="Known fields" value={facts.knownFieldCount} />
                    <FactRow label="Direct ships" value={orbitShips.length} />
                    <FactRow label="Host-confirmed ships" value={combatOrbitContacts.length} />
                </dl>
                {ownerChanged && postHostState !== null && (
                    <DetailSection title="Post-host ownership">
                        <div className="operational-intel-callout operational-owner-change-callout">
                            <strong>{playerName(postHostState.ownerId, players)}</strong>
                            <span>
                                VCR #{postHostState.vcrId} · T{postHostState.turn}
                                {postHostState.basis !== null ? ` · ${postHostState.basis}` : ""}
                            </span>
                        </div>
                    </DetailSection>
                )}
                {combatOrbitContacts.length > 0 && (
                    <DetailSection title="Host-confirmed presence">
                        <div className="intel-orbit-list">
                            {combatOrbitContacts.map((contact) => (
                                <EvidenceLine
                                    contact={contact}
                                    key={`intel:${contact.track.ship_id}:${contact.point.turn}`}
                                />
                            ))}
                        </div>
                    </DetailSection>
                )}
            </div>
        );
    }

    if (tab === "history") {
        return (
            <div className="operational-tab-section">
                <div className="operational-timeline">
                    <div className="operational-timeline-item is-current">
                        <span>T{intel.turn}</span>
                        <strong>Current dashboard snapshot</strong>
                        <small>
                            Planet factual info turn: {planet.info_turn ?? "unknown"}
                        </small>
                    </div>
                    {ownerChanged && postHostState !== null && (
                        <button
                            className="operational-timeline-item"
                            onClick={() => {
                                window.dispatchEvent(
                                    new CustomEvent("dashboard-event-select", {
                                        detail: {
                                            turn: postHostState.turn,
                                            vcrId: postHostState.vcrId,
                                        },
                                    }),
                                );
                            }}
                            type="button"
                        >
                            <span>T{postHostState.turn}</span>
                            <strong>
                                Owner changed: {playerName(planet.owner_id, players)} → {playerName(postHostState.ownerId, players)}
                            </strong>
                            <small>Host-confirmed after VCR #{postHostState.vcrId}</small>
                        </button>
                    )}
                    {combatOrbitContacts.map(({ track, point }) => (
                        <button
                            className="operational-timeline-item"
                            key={`history:${track.ship_id}:${point.turn}`}
                            onClick={() => openCombatEvent(point)}
                            type="button"
                        >
                            <span>T{point.turn}</span>
                            <strong>Fleet Command confirms ship #{track.ship_id} at this planet</strong>
                            <small>
                                {track.name ?? "Unknown ship"}
                                {point.combat_vcr_id !== null ? ` · VCR #${point.combat_vcr_id}` : ""}
                            </small>
                        </button>
                    ))}
                </div>
                <p className="intel-no-facts operational-roadmap-note">
                    Full per-field planet timeline will be populated from stored historical snapshots in the next history pass.
                </p>
            </div>
        );
    }

    return (
        <div className="operational-tab-section">
            <div className="operational-section-heading">
                <span>Combat evidence</span>
                <strong>{combatOrbitContacts.length}</strong>
            </div>
            {ownerChanged && postHostState !== null && (
                <div className="operational-intel-callout operational-owner-change-callout">
                    <strong>Planet ownership changed after host</strong>
                    <span>
                        {playerName(planet.owner_id, players)} → {playerName(postHostState.ownerId, players)}
                        {" · "}VCR #{postHostState.vcrId}
                    </span>
                </div>
            )}
            {tracksLoading ? (
                <p className="intel-no-facts">Loading combat evidence…</p>
            ) : combatOrbitContacts.length > 0 ? (
                <div className="intel-orbit-list">
                    {combatOrbitContacts.map((contact) => (
                        <EvidenceLine
                            contact={contact}
                            key={`combat-tab:${contact.track.ship_id}:${contact.point.turn}`}
                        />
                    ))}
                </div>
            ) : (
                <p className="intel-no-facts">
                    No post-host ship presence is currently confirmed at this planet by combat evidence.
                </p>
            )}
        </div>
    );
}
