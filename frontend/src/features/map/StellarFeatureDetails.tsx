import type { MapStellarCartographyObservation } from "../../types/intel";
import { DetailSection, FactRow } from "./DetailPrimitives";


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
    return "Star cluster";
}


export function StellarFeatureDetails({
    feature,
}: {
    feature: MapStellarCartographyObservation;
}) {
    const kind = featureKind(feature);
    const title = feature.name ?? `${kind} #${feature.feature_id}`;

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
                        <FactRow
                            label="Intensity"
                            value={numberField(feature, "intensity") ?? "—"}
                        />
                        <FactRow
                            label="Gas"
                            value={
                                stringField(feature, "gas")
                                ?? numberField(feature, "gas")
                                ?? "—"
                            }
                        />
                    </dl>
                </DetailSection>
            )}

            {feature.feature_type === "ion_storm" && (
                <DetailSection title="Ion storm">
                    <dl className="intel-fact-list">
                        <FactRow
                            label="Voltage"
                            value={numberField(feature, "voltage") ?? "—"}
                        />
                        <FactRow
                            label="Heading"
                            value={numberField(feature, "heading") ?? "—"}
                        />
                        <FactRow
                            label="Warp"
                            value={numberField(feature, "warp") ?? "—"}
                        />
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
                        <FactRow
                            label="Parent"
                            value={numberField(feature, "parentid") ?? "—"}
                        />
                    </dl>
                </DetailSection>
            )}

            {feature.feature_type === "star_cluster" && (
                <DetailSection title="Star cluster">
                    <dl className="intel-fact-list">
                        <FactRow
                            label="Temperature"
                            value={numberField(feature, "temp") ?? "—"}
                        />
                        <FactRow
                            label="Mass"
                            value={numberField(feature, "mass") ?? "—"}
                        />
                        <FactRow
                            label="Core radius"
                            value={feature.radius ?? "—"}
                        />
                        <FactRow
                            label="Radiation halo"
                            value={(() => {
                                const mass = numberField(feature, "mass");
                                return mass !== null && mass > 0
                                    ? Math.sqrt(mass).toFixed(1)
                                    : "—";
                            })()}
                        />
                        <FactRow
                            label="Planets"
                            value={numberField(feature, "planets") ?? "—"}
                        />
                    </dl>
                </DetailSection>
            )}
        </>
    );
}
