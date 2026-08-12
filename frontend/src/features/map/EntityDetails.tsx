import type { PlayerInfo } from "../../types/api";
import {
    isCombinedPrivateIntel,
    type IntelEntityProvenance,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import { DetailSection } from "./DetailPrimitives";
import { PlanetDetails } from "./PlanetDetails";
import { ShipDetails } from "./ShipDetails";
import { StarbaseDetails } from "./StarbaseDetails";
import { StellarFeatureDetails } from "./StellarFeatureDetails";

function EntityProvenance({
    selected,
    intel,
}: {
    selected: SelectedEntity;
    intel: PrivateIntelMapResponse;
}) {
    const provenance: IntelEntityProvenance[] | undefined =
        selected.value.provenance;

    if (!provenance || provenance.length === 0) {
        return null;
    }

    const fieldCounts = new Map<number, number>();
    for (const sourceAccountId of Object.values(
        selected.value.field_sources ?? {},
    )) {
        fieldCounts.set(
            sourceAccountId,
            (fieldCounts.get(sourceAccountId) ?? 0) + 1,
        );
    }

    return (
        <DetailSection title="Entity provenance">
            {isCombinedPrivateIntel(intel) && fieldCounts.size > 0 && (
                <p className="intel-no-facts" style={{ marginBottom: 8 }}>
                    Field union: {Array.from(fieldCounts.entries())
                        .map(([accountId, count]) => {
                            const source = intel.sources.find(
                                (item) => item.linked_account_id === accountId,
                            );
                            return `${source?.planets_username ?? `account #${accountId}`}: ${count}`;
                        })
                        .join(" · ")}
                </p>
            )}
            <div className="intel-orbit-list">
                {provenance.map((source) => (
                    <div
                        className="intel-orbit-item"
                        key={`${source.linked_account_id}:${source.batch_id}`}
                        style={{ cursor: "default" }}
                    >
                        <span className="intel-orbit-symbol legend-orbit" />
                        <span>
                            <strong>{source.planets_username}</strong>
                            <small>
                                batch #{source.batch_id}
                                {" · "}snapshot turn {source.batch_turn}
                                {" · "}info turn {source.info_turn ?? "—"}
                            </small>
                        </span>
                    </div>
                ))}
            </div>
        </DetailSection>
    );
}

export function EntityDetails({
    selected,
    intel,
    players,
    onSelect,
}: {
    selected: SelectedEntity | null;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    if (selected === null) {
        return (
            <div className="intel-map-empty-selection">
                <strong>Select an entity</strong>
                <p>
                    Click a planet, deep-space ship, nebula, star cluster,
                    or ion storm. Ships in orbit are listed inside the
                    selected planet's Orbit section.
                </p>
            </div>
        );
    }

    let details;

    if (selected.kind === "planet") {
        details = (
            <PlanetDetails
                intel={intel}
                onSelect={onSelect}
                planet={selected.value}
                players={players}
            />
        );
    } else if (selected.kind === "ship") {
        details = (
            <ShipDetails
                intel={intel}
                onSelect={onSelect}
                players={players}
                ship={selected.value}
            />
        );
    } else if (selected.kind === "starbase") {
        details = (
            <StarbaseDetails
                intel={intel}
                onSelect={onSelect}
                starbase={selected.value}
            />
        );
    } else {
        details = (
            <StellarFeatureDetails feature={selected.value} />
        );
    }

    return (
        <>
            {details}
            <EntityProvenance
                intel={intel}
                selected={selected}
            />
        </>
    );
}
