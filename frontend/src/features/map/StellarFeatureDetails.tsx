import type { PlayerInfo } from "../../types/api";
import type {
    MapStellarCartographyObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import {
    minefieldFriendlyCode,
    minefieldIsWeb,
    minefieldOwnerId,
    minefieldSourcePlanet,
    universalMinefieldCodePlanet,
} from "./minefieldAnalysis";
import { planetFacts } from "./observationView";
import { DetailSection, FactRow, playerName } from "./DetailPrimitives";


function numberField(
    feature: MapStellarCartographyObservation,
    key: string,
): number | null {
    const value = feature.payload[key];
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : null;
}

function stringField(
    feature: MapStellarCartographyObservation,
    key: string,
): string | null {
    const value = feature.payload[key];
    return typeof value === "string" && value.trim()
        ? value.trim()
        : null;
}

function booleanField(
    feature: MapStellarCartographyObservation,
    key: string,
): boolean | null {
    const value = feature.payload[key];
    return typeof value === "boolean" ? value : null;
}

function featureKind(feature: MapStellarCartographyObservation): string {
    if (feature.feature_type === "nebula") return "Nebula";
    if (feature.feature_type === "ion_storm") return "Ion storm";
    if (feature.feature_type === "minefield") {
        return minefieldIsWeb(feature) ? "Web minefield" : "Minefield";
    }
    return "Star cluster";
}

export function StellarFeatureDetails({
    feature,
    intel,
    players,
    onSelect,
}: {
    feature: MapStellarCartographyObservation;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    const kind = featureKind(feature);
    const title = feature.name ?? `${kind} #${feature.feature_id}`;

    const mineOwnerId = feature.feature_type === "minefield"
        ? minefieldOwnerId(feature)
        : null;
    const mineSource = feature.feature_type === "minefield"
        ? minefieldSourcePlanet(intel, feature)
        : null;
    const universalPlanet = feature.feature_type === "minefield"
        ? universalMinefieldCodePlanet(intel, feature)
        : null;
    const mineCode = feature.feature_type === "minefield"
        ? minefieldFriendlyCode(feature)
        : null;
    const sourceCode = mineSource !== null
        ? planetFacts(mineSource.planet).friendlyCode
        : null;

    return (
        <>
            <div>
                <span className="intel-entity-kind">{kind}</span>
                <h3>{title}</h3>
            </div>

            <DetailSection title="Map feature">
                <dl className="intel-fact-list">
                    <FactRow label="ID" value={feature.feature_id} />
                    <FactRow label="X" value={feature.x ?? "—"} />
                    <FactRow label="Y" value={feature.y ?? "—"} />
                    <FactRow label="Radius" value={feature.radius ?? "—"} />
                </dl>
            </DetailSection>

            {feature.feature_type === "nebula" && (
                <DetailSection title="Nebula">
                    <dl className="intel-fact-list">
                        <FactRow label="Intensity" value={numberField(feature, "intensity") ?? "—"} />
                        <FactRow
                            label="Gas"
                            value={stringField(feature, "gas") ?? numberField(feature, "gas") ?? "—"}
                        />
                    </dl>
                </DetailSection>
            )}

            {feature.feature_type === "ion_storm" && (
                <DetailSection title="Ion storm">
                    <dl className="intel-fact-list">
                        <FactRow label="Voltage" value={numberField(feature, "voltage") ?? "—"} />
                        <FactRow label="Heading" value={numberField(feature, "heading") ?? "—"} />
                        <FactRow label="Warp" value={numberField(feature, "warp") ?? "—"} />
                        <FactRow
                            label="Growing"
                            value={
                                booleanField(feature, "isgrowing") === null
                                    ? "—"
                                    : booleanField(feature, "isgrowing")
                                        ? "Yes"
                                        : "No"
                            }
                        />
                        <FactRow label="Parent" value={numberField(feature, "parentid") ?? "—"} />
                    </dl>
                </DetailSection>
            )}

            {feature.feature_type === "star_cluster" && (
                <DetailSection title="Star cluster">
                    <dl className="intel-fact-list">
                        <FactRow label="Temperature" value={numberField(feature, "temp") ?? "—"} />
                        <FactRow label="Mass" value={numberField(feature, "mass") ?? "—"} />
                        <FactRow label="Core radius" value={feature.radius ?? "—"} />
                        <FactRow
                            label="Radiation halo"
                            value={(() => {
                                const mass = numberField(feature, "mass");
                                return mass !== null && mass > 0
                                    ? Math.sqrt(mass).toFixed(1)
                                    : "—";
                            })()}
                        />
                        <FactRow label="Planets" value={numberField(feature, "planets") ?? "—"} />
                    </dl>
                </DetailSection>
            )}

            {feature.feature_type === "minefield" && (
                <>
                    <DetailSection title="Minefield">
                        <dl className="intel-fact-list">
                            <FactRow label="Owner" value={playerName(mineOwnerId, players)} />
                            <FactRow label="Type" value={minefieldIsWeb(feature) ? "Web" : "Normal"} />
                            <FactRow label="Observed field code" value={mineCode ?? "—"} />
                        </dl>
                    </DetailSection>

                    <DetailSection title="Friendly-code source">
                        {mineSource !== null ? (
                            <div className="intel-orbit-list">
                                <button
                                    className="intel-orbit-item"
                                    onClick={() => onSelect({
                                        kind: "planet",
                                        value: mineSource.planet,
                                    })}
                                    type="button"
                                >
                                    <span className="intel-orbit-symbol legend-orbit" />
                                    <span>
                                        <strong>
                                            {mineSource.planet.name
                                                ?? `Planet #${mineSource.planet.planet_id}`}
                                        </strong>
                                        <small>
                                            nearest owner planet · {mineSource.distance.toFixed(1)} ly from field center
                                        </small>
                                        <small>
                                            observed FC: {sourceCode ?? "unknown"}
                                        </small>
                                    </span>
                                </button>
                            </div>
                        ) : (
                            <p className="intel-no-facts">
                                The nearest owner planet cannot be determined from the currently combined factual map.
                            </p>
                        )}
                        <p className="intel-no-facts" style={{ marginTop: 8 }}>
                            Planets.nu derives a normal minefield's code from the minefield owner's planet nearest its center. For Bird Men Super Spy Deluxe, this is the direct planet to watch or target when trying to change that field code.
                        </p>
                    </DetailSection>

                    <DetailSection title="Universal MFx bypass">
                        {universalPlanet !== null ? (
                            <button
                                className="intel-orbit-item"
                                onClick={() => onSelect({
                                    kind: "planet",
                                    value: universalPlanet,
                                })}
                                type="button"
                            >
                                <span className="intel-orbit-symbol legend-orbit" />
                                <span>
                                    <strong>
                                        {universalPlanet.name
                                            ?? `Planet #${universalPlanet.planet_id}`}
                                    </strong>
                                    <small>
                                        observed FC {planetFacts(universalPlanet).friendlyCode} · highest-ID observed MFx planet
                                    </small>
                                </span>
                            </button>
                        ) : (
                            <p className="intel-no-facts">
                                No observed owner planet currently has an MFx code.
                            </p>
                        )}
                        <p className="intel-no-facts" style={{ marginTop: 8 }}>
                            Bird Men can use Super Spy Deluxe to set an enemy planet to an MFx code and then use that same case-sensitive code on ships for universal passage through that owner's normal minefields. Modern Standard web fields do not honor this bypass.
                        </p>
                    </DetailSection>
                </>
            )}
        </>
    );
}
