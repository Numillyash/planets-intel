import { useEffect, useState } from "react";

import type { PlayerInfo } from "../../types/api";
import {
    isCombinedPrivateIntel,
    type IntelEntityProvenance,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { DetailSection, playerName } from "./DetailPrimitives";
import { EntityIcon } from "./EntityIcon";
import type { SelectedEntity } from "./mapModel";
import {
    OperationalPlanetPanel,
    type PlanetOperationalTab,
} from "./OperationalPlanetPanel";
import { usePlanetPostHostState } from "./planetPostHostState";
import { ShipDetails } from "./ShipDetails";
import { StarbaseDetails } from "./StarbaseDetails";
import { StellarFeatureDetails } from "./StellarFeatureDetails";
import "./operational-ui.css";

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

const PLANET_TABS: Array<{
    id: PlanetOperationalTab;
    label: string;
}> = [
    { id: "planet", label: "Planet" },
    { id: "economy", label: "Economy" },
    { id: "ships", label: "Ships" },
    { id: "intel", label: "Intel" },
    { id: "history", label: "History" },
    { id: "combat", label: "Combat" },
];

function PlanetOperationalDetails({
    selected,
    intel,
    players,
    onSelect,
}: {
    selected: Extract<SelectedEntity, { kind: "planet" }>;
    intel: PrivateIntelMapResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity | null) => void;
}) {
    const [activeTab, setActiveTab] =
        useState<PlanetOperationalTab>("planet");
    const planet = selected.value;
    const postHostState = usePlanetPostHostState(intel, planet.planet_id);
    const effectiveOwnerId = postHostState?.ownerId ?? planet.owner_id;

    useEffect(() => {
        setActiveTab("planet");
    }, [planet.planet_id]);

    const position =
        planet.x !== null && planet.y !== null
            ? `${planet.x}, ${planet.y}`
            : "position unknown";

    return (
        <div className="operational-entity-panel">
            <header className="operational-entity-header">
                <div className="operational-entity-title-row">
                    <EntityIcon selected={selected} />
                    <div>
                        <span className="operational-entity-kind">Planet</span>
                        <h3>{planet.name ?? `Planet ${planet.planet_id}`}</h3>
                        <p>
                            Planet #{planet.planet_id}
                            {" · "}{playerName(effectiveOwnerId, players)}
                            {" · "}{position}
                        </p>
                        {postHostState !== null && postHostState.ownerId !== planet.owner_id && (
                            <p className="operational-post-host-owner-note">
                                Host-confirmed owner after VCR #{postHostState.vcrId};
                                snapshot owner was {" "}
                                {playerName(planet.owner_id, players)}.
                            </p>
                        )}
                    </div>
                </div>
            </header>

            <nav
                className="operational-entity-tabs"
                aria-label="Planet interface tabs"
            >
                {PLANET_TABS.map((tab) => (
                    <button
                        className={
                            "operational-entity-tab"
                            + (activeTab === tab.id ? " is-active" : "")
                        }
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        type="button"
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            <div className="operational-entity-content">
                <OperationalPlanetPanel
                    intel={intel}
                    onSelect={(entity) => onSelect(entity)}
                    planet={planet}
                    players={players}
                    postHostState={postHostState}
                    tab={activeTab}
                />

                {activeTab === "intel" && (
                    <EntityProvenance intel={intel} selected={selected} />
                )}
            </div>
        </div>
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
    onSelect: (entity: SelectedEntity | null) => void;
}) {
    useEffect(() => {
        if (selected === null) return;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                onSelect(null);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => {
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [onSelect, selected]);

    if (selected === null) {
        return (
            <div className="operational-empty-selection">
                <span className="operational-empty-icon">◉</span>
                <strong>Select an entity</strong>
                <p>
                    Select a planet or ship on the map. The operational panel
                    keeps game-state data and intelligence evidence in separate tabs.
                </p>
            </div>
        );
    }

    const content = selected.kind === "planet" ? (
        <PlanetOperationalDetails
            intel={intel}
            onSelect={onSelect}
            players={players}
            selected={selected}
        />
    ) : selected.kind === "ship" ? (
        <ShipDetails
            intel={intel}
            onSelect={(entity) => onSelect(entity)}
            players={players}
            ship={selected.value}
        />
    ) : selected.kind === "stellar" ? (
        <StellarFeatureDetails
            feature={selected.value}
            intel={intel}
            onSelect={(entity) => onSelect(entity)}
            players={players}
        />
    ) : (
        <>
            <StarbaseDetails
                intel={intel}
                onSelect={(entity) => onSelect(entity)}
                starbase={selected.value}
            />
            <EntityProvenance intel={intel} selected={selected} />
        </>
    );

    return (
        <div className="operational-entity-details-shell">
            <button
                aria-label="Close selected entity"
                className="operational-entity-close"
                onClick={() => onSelect(null)}
                title="Close (Esc)"
                type="button"
            >
                ×
            </button>
            {content}
        </div>
    );
}
