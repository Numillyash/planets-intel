import { useEffect, useRef, useState } from "react";
import type { LatestPrivateIntelResponse, PlayerInfo } from "../../types/api";
import { PLANET_LINK_RANGE, type PlanetLabelMode, type SelectedEntity } from "./mapModel";
import { EntityDetails } from "./EntityDetails";
import { PixiMapCanvas } from "./PixiMapCanvas";
import "./map.css";

interface PrivateIntelMapProps {
    intel: LatestPrivateIntelResponse | null;
    loading: boolean;
    error: string | null;
    observerName: string;
    players: PlayerInfo[];
}

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

export function PrivateIntelMap({
    intel,
    loading,
    error,
    observerName,
    players,
}: PrivateIntelMapProps) {
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const [labelMode, setLabelMode] = useState<PlanetLabelMode>("none");
    const fitViewRef = useRef<(() => void) | null>(null);

    useEffect(() => {
        setSelected(null);
    }, [intel?.observation.batch_id]);

    if (loading) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Loading observer-specific factual observations…</p>
                    </div>
                </div>
                <div className="intel-map-state">Loading private intelligence…</div>
            </section>
        );
    }

    if (error !== null) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Observer: {observerName}</p>
                    </div>
                </div>
                <div className="intel-map-state intel-map-state-error">
                    {error}
                </div>
            </section>
        );
    }

    if (intel === null) {
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

    const selection = selectedLabel(selected);

    return (
        <section className="panel intel-map-panel">
            <div className="panel-header intel-map-header">
                <div>
                    <h2>Private intelligence map</h2>
                    <p>
                        Observer: <strong>{intel.observer.planets_username}</strong>
                        {" · "}Turn {intel.turn}
                        {" · "}Observed {formatObservedAt(intel.observation.observed_at)}
                    </p>
                </div>
                <div className="intel-map-actions">
                    <span>{intel.counts.planets} planets</span>
                    <span>{intel.counts.ships} ships</span>
                    <span>{intel.counts.starbases} bases</span>
                    {selection !== null && (
                        <span className="intel-detail-badge">{selection}</span>
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
                        intel={intel}
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
                        intel={intel}
                        onSelect={setSelected}
                        players={players}
                        selected={selected}
                    />
                    <div className="intel-provenance-note">
                        <strong>Provenance</strong>
                        <span>
                            linked account #{intel.observer.linked_account_id}
                            {" · "}player slot {intel.observer.player_slot_id}
                        </span>
                        <span>
                            batch #{intel.observation.batch_id}
                            {" · "}{intel.observation.source}
                        </span>
                    </div>
                </aside>
            </div>
        </section>
    );
}
