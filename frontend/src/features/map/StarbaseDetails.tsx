import { useEffect, useState } from "react";

import {
    isCombinedPrivateIntel,
    isPublicArchiveIntel,
    type MapStarbaseObservation,
    type GameMapIntelSource,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import {
    formatInteger,
    formatPercent,
    planetFacts,
    starbaseFacts,
} from "./observationView";
import { DetailSection, FactRow } from "./DetailPrimitives";
import { EntityIcon } from "./EntityIcon";
import { StarbaseOrderDraftPanel } from "./EntityOrderDraftPanels";


type StarbaseTab = "status" | "orders";

function payloadText(
    payload: Record<string, unknown>,
    ...keys: string[]
): string | null {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, value] of Object.entries(payload)) {
        if (!wanted.has(key.toLowerCase())) continue;
        if (typeof value === "string" && value.trim()) return value.trim();
        if (typeof value === "number") return String(value);
    }
    return null;
}

export function StarbaseDetails({
    starbase,
    intel,
    onSelect,
}: {
    starbase: MapStarbaseObservation;
    intel: GameMapIntelSource;
    onSelect: (entity: SelectedEntity) => void;
}) {
    const [activeTab, setActiveTab] = useState<StarbaseTab>("status");
    const facts = starbaseFacts(starbase);
    const planet = intel.planets.find(
        (item) => item.planet_id === starbase.planet_id,
    ) ?? null;
    const readOnly = isPublicArchiveIntel(intel);
    const linkedAccountId = readOnly ? null
        : isCombinedPrivateIntel(intel)
            ? intel.primary_observer.linked_account_id
            : intel.observer.linked_account_id;
    const primarySlotId = readOnly ? intel.player_slot_id
        : isCombinedPrivateIntel(intel)
            ? intel.primary_observer.player_slot_id
            : intel.observer.player_slot_id;
    const ownBase = !readOnly && planet !== null && planet.owner_id === primarySlotId;
    const upstreamPrimaryOrder = payloadText(
        starbase.payload,
        "missionname",
        "primaryordername",
        "primary_order_name",
        "ordername",
        "mission",
        "primaryorder",
    );
    const upstreamFriendlyCode = planet !== null
        ? planetFacts(planet).friendlyCode
        : null;

    useEffect(() => {
        setActiveTab("status");
    }, [starbase.starbase_id]);

    return (
        <div className="operational-entity-panel">
            <header className="operational-entity-header">
                <div className="operational-entity-title-row">
                    <EntityIcon selected={{ kind: "starbase", value: starbase }} />
                    <div>
                        <span className="operational-entity-kind">Starbase</span>
                        <h3>{facts.name ?? `Starbase ${starbase.starbase_id}`}</h3>
                        <p>
                            Base #{starbase.starbase_id}
                            {planet !== null
                                ? ` · ${planet.name ?? `Planet #${planet.planet_id}`}`
                                : ""}
                        </p>
                    </div>
                </div>
            </header>

            {planet !== null && (
                <button
                    className="intel-detail-badge intel-detail-badge-button"
                    onClick={() => onSelect({ kind: "planet", value: planet })}
                    type="button"
                >
                    Orbiting {planet.name ?? `Planet ${planet.planet_id}`}
                </button>
            )}

            <nav className="operational-entity-tabs" role="tablist" aria-label="Starbase details">
                <button
                    className={`operational-entity-tab${activeTab === "status" ? " is-active" : ""}`}
                    onClick={() => setActiveTab("status")}
                    type="button"
                >
                    Status
                </button>
                {!readOnly && <button
                    className={`operational-entity-tab${activeTab === "orders" ? " is-active" : ""}`}
                    onClick={() => setActiveTab("orders")}
                    type="button"
                >
                    Orders
                </button>}
            </nav>

            <div className="operational-entity-content">
                {activeTab === "status" && (
                    <>
                        <DetailSection title="Starbase status">
                            <dl className="intel-fact-list">
                                <FactRow label="ID" value={starbase.starbase_id} />
                                <FactRow label="Planet ID" value={starbase.planet_id ?? "—"} />
                                <FactRow label="Race ID" value={starbase.race_id ?? "—"} />
                                <FactRow label="Primary order" value={upstreamPrimaryOrder ?? "—"} />
                                <FactRow label="Friendly code" value={upstreamFriendlyCode ?? "—"} />
                                <FactRow label="Damage" value={formatPercent(facts.damage)} />
                                <FactRow label="Defense" value={formatInteger(facts.defense)} />
                                <FactRow label="Fighters" value={formatInteger(facts.fighters)} />
                                <FactRow label="Info turn" value={starbase.info_turn ?? "—"} />
                            </dl>
                        </DetailSection>

                        <DetailSection title="Tech levels">
                            <dl className="intel-fact-list">
                                <FactRow label="Hull" value={facts.hullTech ?? "—"} />
                                <FactRow label="Engine" value={facts.engineTech ?? "—"} />
                                <FactRow label="Beam" value={facts.beamTech ?? "—"} />
                                <FactRow label="Torpedo" value={facts.torpedoTech ?? "—"} />
                            </dl>
                        </DetailSection>
                    </>
                )}

                {activeTab === "orders" && (
                    ownBase && planet !== null && linkedAccountId !== null ? (
                        <StarbaseOrderDraftPanel
                            gameId={intel.game_id}
                            linkedAccountId={linkedAccountId}
                            planetId={planet.planet_id}
                            starbaseId={starbase.starbase_id}
                            turn={intel.turn}
                            upstreamFriendlyCode={upstreamFriendlyCode}
                            upstreamPrimaryOrder={upstreamPrimaryOrder}
                        />
                    ) : (
                        <p className="intel-no-facts">Orders are editable only for your own starbase on the latest factual turn.</p>
                    )
                )}
            </div>
        </div>
    );
}
