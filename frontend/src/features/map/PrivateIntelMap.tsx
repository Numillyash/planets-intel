import {
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import { getCombinedPrivateIntel } from "../../api/client";
import type { PlayerInfo } from "../../types/api";
import {
    isCombinedPrivateIntel,
    type CombinedPrivateIntelResponse,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { PLANET_LINK_RANGE, type PlanetLabelMode, type SelectedEntity } from "./mapModel";
import { EntityDetails } from "./EntityDetails";
import { PixiMapCanvas } from "./PixiMapCanvas";
import "./map.css";

interface PrivateIntelMapProps {
    intel: PrivateIntelMapResponse | null;
    loading: boolean;
    error: string | null;
    observerName: string;
    players: PlayerInfo[];
}

type IntelViewMode = "observer" | "combined";

function formatObservedAt(value: string): string {
    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleString();
}

function selectedLabel(selected: SelectedEntity | null): string | null {
    if (selected === null) {
        return null;
    }

    if (selected.kind === "planet") {
        return `Selected: ${selected.value.name ?? `Planet #${selected.value.planet_id}`}`;
    }

    if (selected.kind === "ship") {
        return `Selected: ${selected.value.name ?? `Ship #${selected.value.ship_id}`}`;
    }

    return `Selected: Starbase #${selected.value.starbase_id}`;
}

function intelRevisionKey(intel: PrivateIntelMapResponse | null): string {
    if (intel === null) {
        return "none";
    }

    if (isCombinedPrivateIntel(intel)) {
        return `combined:${intel.sources
            .map((source) => `${source.linked_account_id}:${source.batch_id}`)
            .join("|")}`;
    }

    return `observer:${intel.observation.batch_id}`;
}

function primaryIdentity(intel: PrivateIntelMapResponse | null): {
    gameId: number;
    linkedAccountId: number;
    revision: string;
} | null {
    if (intel === null) {
        return null;
    }

    if (isCombinedPrivateIntel(intel)) {
        return {
            gameId: intel.game_id,
            linkedAccountId: intel.primary_observer.linked_account_id,
            revision: intelRevisionKey(intel),
        };
    }

    return {
        gameId: intel.game_id,
        linkedAccountId: intel.observer.linked_account_id,
        revision: intelRevisionKey(intel),
    };
}

function latestCombinedObservedAt(
    intel: CombinedPrivateIntelResponse,
): string | null {
    let latest: { value: string; timestamp: number } | null = null;

    for (const source of intel.sources) {
        const timestamp = new Date(source.observed_at).getTime();
        const normalizedTimestamp = Number.isNaN(timestamp) ? 0 : timestamp;

        if (latest === null || normalizedTimestamp > latest.timestamp) {
            latest = {
                value: source.observed_at,
                timestamp: normalizedTimestamp,
            };
        }
    }

    return latest?.value ?? null;
}

export function PrivateIntelMap({
    intel,
    loading,
    error,
    observerName,
    players,
}: PrivateIntelMapProps) {
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const [labelMode, setLabelMode] = useState<PlanetLabelMode>("none");
    const [viewMode, setViewMode] = useState<IntelViewMode>("observer");
    const [combinedIntel, setCombinedIntel] =
        useState<CombinedPrivateIntelResponse | null>(null);
    const [combinedLoading, setCombinedLoading] = useState(false);
    const [combinedError, setCombinedError] = useState<string | null>(null);
    const [sharingRevision, setSharingRevision] = useState(0);
    const fitViewRef = useRef<(() => void) | null>(null);

    const identity = useMemo(
        () => primaryIdentity(intel),
        [intel],
    );

    useEffect(() => {
        const handleSharesChanged = () => {
            setSharingRevision((value) => value + 1);
        };

        window.addEventListener(
            "dashboard-intel-shares-changed",
            handleSharesChanged,
        );

        return () => {
            window.removeEventListener(
                "dashboard-intel-shares-changed",
                handleSharesChanged,
            );
        };
    }, []);

    useEffect(() => {
        let cancelled = false;

        if (viewMode !== "combined" || identity === null) {
            setCombinedIntel(null);
            setCombinedError(null);
            setCombinedLoading(false);
            return () => {
                cancelled = true;
            };
        }

        const combinedIdentity = identity;

        async function loadCombined() {
            setCombinedLoading(true);
            setCombinedError(null);

            try {
                const response = await getCombinedPrivateIntel(
                    combinedIdentity.gameId,
                    combinedIdentity.linkedAccountId,
                );

                if (!cancelled) {
                    setCombinedIntel(response);
                }
            } catch (reason) {
                if (!cancelled) {
                    setCombinedIntel(null);
                    setCombinedError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load combined dashboard intelligence",
                    );
                }
            } finally {
                if (!cancelled) {
                    setCombinedLoading(false);
                }
            }
        }

        void loadCombined();

        return () => {
            cancelled = true;
        };
    }, [
        identity?.gameId,
        identity?.linkedAccountId,
        identity?.revision,
        sharingRevision,
        viewMode,
    ]);

    const displayIntel: PrivateIntelMapResponse | null =
        viewMode === "combined"
            ? combinedIntel
            : intel;

    const effectiveLoading =
        loading || (viewMode === "combined" && combinedLoading);
    const effectiveError =
        viewMode === "combined"
            ? combinedError ?? (intel === null ? error : null)
            : error;
    const revisionKey = intelRevisionKey(displayIntel);

    useEffect(() => {
        setSelected(null);
    }, [revisionKey, viewMode]);

    if (effectiveLoading) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Loading factual observations…</p>
                    </div>
                </div>
                <div className="intel-map-state">Loading private intelligence…</div>
            </section>
        );
    }

    if (effectiveError !== null) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Observer: {observerName}</p>
                    </div>
                </div>
                <div className="intel-map-state intel-map-state-error">
                    {effectiveError}
                </div>
            </section>
        );
    }

    if (displayIntel === null) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Observer: {observerName}</p>
                    </div>
                </div>
                <div className="intel-map-state">
                    No private factual snapshot is stored for this observer and game yet.
                </div>
            </section>
        );
    }

    const combined = isCombinedPrivateIntel(displayIntel);
    const primaryObserver = combined
        ? displayIntel.primary_observer
        : displayIntel.observer;
    const latestObservedAt = combined
        ? latestCombinedObservedAt(displayIntel)
        : displayIntel.observation.observed_at;
    const selection = selectedLabel(selected);

    return (
        <section className="panel intel-map-panel">
            <div className="panel-header intel-map-header">
                <div>
                    <h2>
                        {combined
                            ? "Combined dashboard intelligence map"
                            : "Private intelligence map"}
                    </h2>
                    <p>
                        {combined ? "Primary observer" : "Observer"}: {" "}
                        <strong>{primaryObserver.planets_username}</strong>
                        {" · "}Turn {displayIntel.turn}
                        {combined && (
                            ` · ${displayIntel.sources.length} factual source${displayIntel.sources.length === 1 ? "" : "s"}`
                        )}
                        {latestObservedAt !== null && (
                            ` · Observed through ${formatObservedAt(latestObservedAt)}`
                        )}
                    </p>
                </div>
                <div className="intel-map-actions">
                    <span>{displayIntel.counts.planets} planets</span>
                    <span>{displayIntel.counts.ships} ships</span>
                    <span>{displayIntel.counts.starbases} bases</span>
                    {selection !== null && (
                        <span className="intel-detail-badge">{selection}</span>
                    )}
                    <label className="intel-label-control">
                        <span>Intel view</span>
                        <select
                            className="secondary-button"
                            onChange={(event) =>
                                setViewMode(event.target.value as IntelViewMode)
                            }
                            value={viewMode}
                        >
                            <option value="observer">Observer only</option>
                            <option value="combined">Combined dashboard intel</option>
                        </select>
                    </label>
                    {viewMode === "combined" && (
                        <button
                            className="secondary-button"
                            onClick={() =>
                                setSharingRevision((value) => value + 1)
                            }
                            type="button"
                        >
                            Refresh combined
                        </button>
                    )}
                    <label className="intel-label-control">
                        <span>Planet labels</span>
                        <select
                            className="secondary-button"
                            onChange={(event) =>
                                setLabelMode(event.target.value as PlanetLabelMode)
                            }
                            value={labelMode}
                        >
                            <option value="none">None</option>
                            <option value="id">Number</option>
                            <option value="name">Name</option>
                        </select>
                    </label>
                    <button
                        className="secondary-button"
                        onClick={() => fitViewRef.current?.()}
                        type="button"
                    >
                        Fit view
                    </button>
                </div>
            </div>

            <div className="intel-map-layout">
                <div className="intel-map-stage-wrap">
                    <PixiMapCanvas
                        fitViewRef={fitViewRef}
                        intel={displayIntel}
                        labelMode={labelMode}
                        onSelect={setSelected}
                        selected={selected}
                    />
                    <div className="intel-map-help">
                        Drag to pan · wheel to zoom · orbit ring means ships are present
                    </div>
                    <div className="intel-map-legend">
                        <span><i className="legend-link" />≤ {PLANET_LINK_RANGE} ly</span>
                        <span><i className="legend-planet" />Planet</span>
                        <span><i className="legend-starbase" />Planet + base</span>
                        <span><i className="legend-orbit" />Ships in orbit</span>
                        <span><i className="legend-freighter" />Freighter</span>
                        <span><i className="legend-torpedo" />Torpedo</span>
                        <span><i className="legend-carrier" />Carrier</span>
                        <span><i className="legend-warship" />Combat</span>
                    </div>
                </div>

                <aside className="intel-map-details">
                    <div className="eyebrow">Selected factual observation</div>
                    <EntityDetails
                        intel={displayIntel}
                        onSelect={setSelected}
                        players={players}
                        selected={selected}
                    />
                    {combined ? (
                        <div className="intel-provenance-note">
                            <strong>Aggregation provenance</strong>
                            <span>
                                Policy: freshest known factual value per field; no inference
                            </span>
                            {displayIntel.sources.map((source) => (
                                <span key={`${source.linked_account_id}:${source.batch_id}`}>
                                    {source.planets_username}
                                    {" · "}batch #{source.batch_id}
                                    {" · "}turn {source.turn}
                                </span>
                            ))}
                        </div>
                    ) : (
                        <div className="intel-provenance-note">
                            <strong>Provenance</strong>
                            <span>
                                linked account #{displayIntel.observer.linked_account_id}
                                {" · "}player slot {displayIntel.observer.player_slot_id}
                            </span>
                            <span>
                                batch #{displayIntel.observation.batch_id}
                                {" · "}{displayIntel.observation.source}
                            </span>
                        </div>
                    )}
                </aside>
            </div>
        </section>
    );
}
