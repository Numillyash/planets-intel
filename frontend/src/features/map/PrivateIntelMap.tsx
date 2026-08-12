import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import {
    getCombinedPrivateIntel,
    getLatestPrivateIntel,
    refreshAccessiblePrivateIntel,
} from "../../api/client";
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

const AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

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

    if (selected.kind === "starbase") {
        return `Selected: Starbase #${selected.value.starbase_id}`;
    }

    const kind = selected.value.feature_type === "nebula"
        ? "Nebula"
        : selected.value.feature_type === "ion_storm"
            ? "Ion storm"
            : "Star cluster";
    return `Selected: ${selected.value.name ?? `${kind} #${selected.value.feature_id}`}`;
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

function reconcileSelection(
    selected: SelectedEntity | null,
    intel: PrivateIntelMapResponse,
): SelectedEntity | null {
    if (selected === null) {
        return null;
    }

    if (selected.kind === "planet") {
        const value = intel.planets.find(
            (planet) => planet.planet_id === selected.value.planet_id,
        );
        return value ? { kind: "planet", value } : null;
    }

    if (selected.kind === "ship") {
        const value = intel.ships.find(
            (ship) => ship.ship_id === selected.value.ship_id,
        );
        return value ? { kind: "ship", value } : null;
    }

    if (selected.kind === "starbase") {
        const value = intel.starbases.find(
            (starbase) => starbase.starbase_id === selected.value.starbase_id,
        );
        return value ? { kind: "starbase", value } : null;
    }

    const value = intel.stellar_cartography.find(
        (feature) =>
            feature.feature_type === selected.value.feature_type &&
            feature.feature_id === selected.value.feature_id,
    );
    return value ? { kind: "stellar", value } : null;
}

export function PrivateIntelMap({
    intel,
    loading,
    error,
    observerName,
    players,
}: PrivateIntelMapProps) {
    const [observerIntel, setObserverIntel] =
        useState<PrivateIntelMapResponse | null>(intel);
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const [labelMode, setLabelMode] = useState<PlanetLabelMode>("none");
    const [viewMode, setViewMode] = useState<IntelViewMode>("combined");
    const [combinedIntel, setCombinedIntel] =
        useState<CombinedPrivateIntelResponse | null>(null);
    const [combinedLoading, setCombinedLoading] = useState(false);
    const [combinedError, setCombinedError] = useState<string | null>(null);
    const [autoRefreshing, setAutoRefreshing] = useState(false);
    const [autoRefreshError, setAutoRefreshError] = useState<string | null>(null);
    const [sharingRevision, setSharingRevision] = useState(0);
    const fitViewRef = useRef<(() => void) | null>(null);
    const refreshInFlightRef = useRef(false);

    useEffect(() => {
        setObserverIntel(intel);
    }, [intel]);

    const identity = useMemo(
        () => primaryIdentity(observerIntel),
        [observerIntel],
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

    const refreshAllSources = useCallback(async () => {
        const gameId = identity?.gameId ?? null;
        const linkedAccountId = identity?.linkedAccountId ?? null;

        if (
            gameId === null ||
            linkedAccountId === null ||
            refreshInFlightRef.current
        ) {
            return;
        }

        refreshInFlightRef.current = true;
        setAutoRefreshing(true);
        setAutoRefreshError(null);

        try {
            await refreshAccessiblePrivateIntel(gameId);

            const latest = await getLatestPrivateIntel(
                gameId,
                linkedAccountId,
            );
            if (latest !== null) {
                setObserverIntel(latest);
            }

            // Peers can change even if the primary snapshot hash is unchanged.
            setSharingRevision((value) => value + 1);
        } catch (reason) {
            setAutoRefreshError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to refresh accessible private intelligence",
            );
        } finally {
            refreshInFlightRef.current = false;
            setAutoRefreshing(false);
        }
    }, [identity?.gameId, identity?.linkedAccountId]);

    useEffect(() => {
        if (identity === null) {
            return;
        }

        void refreshAllSources();
        const intervalId = window.setInterval(
            () => void refreshAllSources(),
            AUTO_REFRESH_INTERVAL_MS,
        );

        return () => {
            window.clearInterval(intervalId);
        };
    }, [
        identity?.gameId,
        identity?.linkedAccountId,
        refreshAllSources,
    ]);

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
            : observerIntel;

    const effectiveLoading =
        displayIntel === null &&
        (loading || (viewMode === "combined" && combinedLoading));
    const effectiveError =
        viewMode === "combined"
            ? combinedError
                ?? autoRefreshError
                ?? (observerIntel === null ? error : null)
            : autoRefreshError ?? error;
    const revisionKey = intelRevisionKey(displayIntel);

    useEffect(() => {
        if (displayIntel === null) {
            setSelected(null);
            return;
        }

        setSelected((current) => reconcileSelection(current, displayIntel));
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

    if (effectiveError !== null && displayIntel === null) {
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
                    {effectiveError !== null && (
                        <p style={{ color: "#d88787", marginTop: 6 }}>
                            Refresh warning: {effectiveError}
                        </p>
                    )}
                </div>
                <div className="intel-map-actions">
                    <span>{displayIntel.counts.planets} planets</span>
                    <span>{displayIntel.counts.ships} ships</span>
                    <span>{displayIntel.counts.starbases} bases</span>
                    <span>{displayIntel.counts.nebulas} nebulae</span>
                    <span>{displayIntel.counts.star_clusters} clusters</span>
                    <span>{displayIntel.counts.ion_storms} storms</span>
                    <span>
                        Auto refresh 5 min{autoRefreshing ? " · updating…" : ""}
                    </span>
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
                            <option value="combined">Combined dashboard intel</option>
                            <option value="observer">Observer only</option>
                        </select>
                    </label>
                    <button
                        className="secondary-button"
                        disabled={autoRefreshing}
                        onClick={() => void refreshAllSources()}
                        type="button"
                    >
                        {autoRefreshing ? "Refreshing all…" : "Refresh all intel"}
                    </button>
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
                        <span>
                            <i style={{ border: "1px solid #5c9cca", borderRadius: "50%", background: "rgba(63,127,174,.35)" }} />
                            Nebula
                        </span>
                        <span>
                            <i style={{ border: "1px solid #d7e4f5", borderRadius: "50%", background: "rgba(215,228,245,.35)" }} />
                            Star cluster
                        </span>
                        <span>
                            <i style={{ border: "1px solid #e8c95d", borderRadius: "50%", background: "rgba(231,189,61,.35)" }} />
                            Ion storm
                        </span>
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
