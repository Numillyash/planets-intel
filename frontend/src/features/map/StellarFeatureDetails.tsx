import { useEffect, useMemo, useState } from "react";

import type { PlayerInfo } from "../../types/api";
import type {
    IntelEntityProvenance,
    MapStellarCartographyObservation,
    GameMapIntelSource,
} from "../../types/intel";
import type { SelectedEntity } from "./mapModel";
import {
    minefieldFriendlyCode,
    minefieldIsWeb,
    minefieldOwnerId,
    minefieldSourcePlanet,
    universalMinefieldCodePlanet,
} from "./minefieldAnalysis";
import { ionStormAtPoint } from "./navigationAnalysis";
import { planetFacts } from "./observationView";
import { DetailSection, FactRow, playerName } from "./DetailPrimitives";


type StellarTab = "overview" | "analysis" | "intel";


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

function featureSymbol(feature: MapStellarCartographyObservation): string {
    if (feature.feature_type === "minefield") return minefieldIsWeb(feature) ? "✺" : "✹";
    if (feature.feature_type === "ion_storm") return "ϟ";
    if (feature.feature_type === "nebula") return "☁";
    return "✦";
}

function analysisLabel(feature: MapStellarCartographyObservation): string {
    if (feature.feature_type === "minefield") return "Codes";
    if (feature.feature_type === "ion_storm") return "Hazard";
    if (feature.feature_type === "star_cluster") return "Radiation";
    return "Environment";
}

function overviewLabel(feature: MapStellarCartographyObservation): string {
    if (feature.feature_type === "minefield") return "Field";
    if (feature.feature_type === "ion_storm") return "Storm";
    if (feature.feature_type === "star_cluster") return "Cluster";
    return "Nebula";
}

function ProvenancePanel({
    feature,
    intel,
}: {
    feature: MapStellarCartographyObservation;
    intel: GameMapIntelSource;
}) {
    const provenance: IntelEntityProvenance[] = feature.provenance ?? [];
    const fieldCounts = new Map<number, number>();

    for (const sourceAccountId of Object.values(feature.field_sources ?? {})) {
        fieldCounts.set(
            sourceAccountId,
            (fieldCounts.get(sourceAccountId) ?? 0) + 1,
        );
    }

    return (
        <div className="operational-tab-section">
            {fieldCounts.size > 0 && "sources" in intel && (
                <div className="operational-intel-callout">
                    <strong>Combined factual field union</strong>
                    <span>
                        {Array.from(fieldCounts.entries()).map(([accountId, count]) => {
                            const source = intel.sources.find(
                                (item) => item.linked_account_id === accountId,
                            );
                            return `${source?.planets_username ?? `account #${accountId}`}: ${count}`;
                        }).join(" · ")}
                    </span>
                </div>
            )}

            <DetailSection title="Entity provenance">
                {provenance.length === 0 ? (
                    <p className="intel-no-facts">No source provenance is attached to this map feature.</p>
                ) : (
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
                )}
            </DetailSection>
        </div>
    );
}


export function StellarFeatureDetails({
    feature,
    intel,
    players,
    onSelect,
}: {
    feature: MapStellarCartographyObservation;
    intel: GameMapIntelSource;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    const [activeTab, setActiveTab] = useState<StellarTab>("overview");
    const kind = featureKind(feature);
    const title = feature.name ?? `${kind} #${feature.feature_id}`;

    useEffect(() => {
        setActiveTab("overview");
    }, [feature.feature_id, feature.feature_type]);

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

    const ionHazard = useMemo(() => {
        if (
            feature.feature_type !== "ion_storm" ||
            feature.x === null ||
            feature.y === null
        ) {
            return null;
        }
        return ionStormAtPoint(intel, feature.x, feature.y);
    }, [feature, intel]);

    const position = feature.x !== null && feature.y !== null
        ? `${feature.x}, ${feature.y}`
        : "position unknown";

    return (
        <div className="operational-entity-panel">
            <header className="operational-entity-header">
                <div className="operational-entity-title-row">
                    <span
                        aria-hidden="true"
                        className={`operational-feature-icon is-${feature.feature_type}`}
                    >
                        {featureSymbol(feature)}
                    </span>
                    <div>
                        <span className="operational-entity-kind">{kind}</span>
                        <h3>{title}</h3>
                        <p>
                            #{feature.feature_id}
                            {" · "}{position}
                            {feature.radius !== null ? ` · radius ${feature.radius} ly` : ""}
                        </p>
                    </div>
                </div>
            </header>

            <nav className="operational-entity-tabs" aria-label={`${kind} interface tabs`}>
                {([
                    ["overview", overviewLabel(feature)],
                    ["analysis", analysisLabel(feature)],
                    ["intel", "Intel"],
                ] as Array<[StellarTab, string]>).map(([id, label]) => (
                    <button
                        className={
                            "operational-entity-tab"
                            + (activeTab === id ? " is-active" : "")
                        }
                        key={id}
                        onClick={() => setActiveTab(id)}
                        type="button"
                    >
                        {label}
                    </button>
                ))}
            </nav>

            <div className="operational-entity-content">
                {activeTab === "overview" && (
                    <div className="operational-tab-section">
                        <DetailSection title="Map feature">
                            <dl className="intel-fact-list">
                                <FactRow label="ID" value={feature.feature_id} />
                                <FactRow label="Position" value={position} />
                                <FactRow label="Radius" value={feature.radius ?? "—"} />
                            </dl>
                        </DetailSection>

                        {feature.feature_type === "minefield" && (
                            <DetailSection title="Minefield state">
                                <dl className="intel-fact-list">
                                    <FactRow label="Owner" value={playerName(mineOwnerId, players)} />
                                    <FactRow label="Type" value={minefieldIsWeb(feature) ? "Web" : "Normal"} />
                                    <FactRow label="Observed field code" value={mineCode ?? "—"} />
                                </dl>
                            </DetailSection>
                        )}

                        {feature.feature_type === "ion_storm" && (
                            <DetailSection title="Storm state">
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
                            <DetailSection title="Cluster state">
                                <dl className="intel-fact-list">
                                    <FactRow label="Temperature" value={numberField(feature, "temp") ?? "—"} />
                                    <FactRow label="Mass" value={numberField(feature, "mass") ?? "—"} />
                                    <FactRow label="Planets" value={numberField(feature, "planets") ?? "—"} />
                                </dl>
                            </DetailSection>
                        )}

                        {feature.feature_type === "nebula" && (
                            <DetailSection title="Nebula state">
                                <dl className="intel-fact-list">
                                    <FactRow label="Intensity" value={numberField(feature, "intensity") ?? "—"} />
                                    <FactRow
                                        label="Gas"
                                        value={stringField(feature, "gas") ?? numberField(feature, "gas") ?? "—"}
                                    />
                                </dl>
                            </DetailSection>
                        )}
                    </div>
                )}

                {activeTab === "analysis" && feature.feature_type === "minefield" && (
                    <div className="operational-tab-section">
                        <DetailSection title="Friendly-code source">
                            {mineSource !== null ? (
                                <div className="intel-orbit-list">
                                    <button
                                        className="intel-orbit-item"
                                        onClick={() => onSelect({ kind: "planet", value: mineSource.planet })}
                                        type="button"
                                    >
                                        <span className="intel-orbit-symbol legend-orbit" />
                                        <span>
                                            <strong>
                                                {mineSource.planet.name ?? `Planet #${mineSource.planet.planet_id}`}
                                            </strong>
                                            <small>
                                                nearest owner planet · {mineSource.distance.toFixed(1)} ly from field center
                                            </small>
                                            <small>observed FC: {sourceCode ?? "unknown"}</small>
                                        </span>
                                    </button>
                                </div>
                            ) : (
                                <p className="intel-no-facts">
                                    The nearest owner planet cannot be determined from the current combined factual map.
                                </p>
                            )}
                        </DetailSection>

                        <DetailSection title="Universal MFx bypass">
                            {universalPlanet !== null ? (
                                <button
                                    className="intel-orbit-item"
                                    onClick={() => onSelect({ kind: "planet", value: universalPlanet })}
                                    type="button"
                                >
                                    <span className="intel-orbit-symbol legend-orbit" />
                                    <span>
                                        <strong>
                                            {universalPlanet.name ?? `Planet #${universalPlanet.planet_id}`}
                                        </strong>
                                        <small>
                                            observed FC {planetFacts(universalPlanet).friendlyCode} · highest-ID observed MFx planet
                                        </small>
                                    </span>
                                </button>
                            ) : (
                                <p className="intel-no-facts">No observed owner planet currently has an MFx code.</p>
                            )}
                        </DetailSection>
                    </div>
                )}

                {activeTab === "analysis" && feature.feature_type === "ion_storm" && (
                    <div className="operational-tab-section">
                        <div className="operational-summary-grid">
                            <div><span>Class</span><strong>{ionHazard?.stormClass ?? "—"}</strong></div>
                            <div><span>Local voltage</span><strong>{ionHazard !== null ? `${Math.round(ionHazard.localVoltage)} meV` : "—"}</strong></div>
                            <div><span>Drag distance</span><strong>{ionHazard?.dragDistance !== null && ionHazard?.dragDistance !== undefined ? `${ionHazard.dragDistance.toFixed(1)} ly` : "—"}</strong></div>
                            <div><span>Cloudy</span><strong>{ionHazard === null ? "—" : ionHazard.cloudy ? "Yes" : "No"}</strong></div>
                        </div>
                        <div className="operational-intel-callout">
                            <strong>
                                {ionHazard?.extremeTransportRisk
                                    ? "Extreme transport risk"
                                    : ionHazard?.randomTransportRisk
                                        ? "Random transport risk"
                                        : "No random transport trigger at storm center"}
                            </strong>
                            <span>
                                Hazard values are derived from the factual storm circles currently visible to this observer set.
                            </span>
                        </div>
                    </div>
                )}

                {activeTab === "analysis" && feature.feature_type === "star_cluster" && (
                    <div className="operational-tab-section">
                        <DetailSection title="Radiation geometry">
                            <dl className="intel-fact-list">
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
                            </dl>
                        </DetailSection>
                    </div>
                )}

                {activeTab === "analysis" && feature.feature_type === "nebula" && (
                    <div className="operational-tab-section">
                        <div className="operational-intel-callout">
                            <strong>Environmental observation</strong>
                            <span>
                                This tab is reserved for nebula-specific navigation and sensor effects once those rules are exposed by the game read model.
                            </span>
                        </div>
                    </div>
                )}

                {activeTab === "intel" && (
                    <ProvenancePanel feature={feature} intel={intel} />
                )}
            </div>
        </div>
    );
}
