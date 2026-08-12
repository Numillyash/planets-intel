import type {
    MapStarbaseObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import { formatInteger, formatPercent, starbaseFacts } from "./observationView";
import { DetailSection, FactRow } from "./DetailPrimitives";

export function StarbaseDetails({
    starbase,
    intel,
    onSelect,
}: {
    starbase: MapStarbaseObservation;
    intel: PrivateIntelMapResponse;
    onSelect: (entity: SelectedEntity) => void;
}) {
    const facts = starbaseFacts(starbase);
    const planet = intel.planets.find(
        (item) => item.planet_id === starbase.planet_id,
    ) ?? null;

    return (
        <div className="intel-entity-details">
            <span className="intel-entity-kind">Starbase</span>
            <h3>{facts.name ?? `Starbase ${starbase.starbase_id}`}</h3>
            {planet !== null && (
                <button
                    className="intel-detail-badge intel-detail-badge-button"
                    onClick={() => onSelect({ kind: "planet", value: planet })}
                    type="button"
                >
                    At {planet.name ?? `Planet ${planet.planet_id}`}
                </button>
            )}

            <DetailSection title="Starbase status">
                <dl className="intel-fact-list">
                    <FactRow label="ID" value={starbase.starbase_id} />
                    <FactRow label="Planet ID" value={starbase.planet_id ?? "—"} />
                    <FactRow label="Race ID" value={starbase.race_id ?? "—"} />
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
        </div>
    );
}
