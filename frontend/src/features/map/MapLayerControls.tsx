import { useState } from "react";

import "./map-layer-controls.css";


export interface MapLayerVisibility {
    entities: boolean;
    minefields: boolean;
    historicalTracks: boolean;
    movementPredictions: boolean;
    combatEvents: boolean;
    hostEvents: boolean;
    spatialMessages: boolean;
}


export const DEFAULT_MAP_LAYER_VISIBILITY: MapLayerVisibility = {
    entities: true,
    minefields: true,
    historicalTracks: true,
    movementPredictions: true,
    combatEvents: true,
    hostEvents: true,
    spatialMessages: false,
};


type MapLayerKey = keyof MapLayerVisibility;


const LAYERS: Array<{
    key: MapLayerKey;
    label: string;
    detail: string;
    provenance: string;
}> = [
    {
        key: "entities",
        label: "Entities",
        detail: "Planets, ships, starbases and Stellar Cartography",
        provenance: "facts",
    },
    {
        key: "minefields",
        label: "Minefields",
        detail: "Observed normal and web minefield geometry",
        provenance: "facts",
    },
    {
        key: "historicalTracks",
        label: "Historical tracks",
        detail: "Stored factual ship-position history",
        provenance: "history",
    },
    {
        key: "movementPredictions",
        label: "Movement",
        detail: "Local drafts and bounded movement prediction",
        provenance: "derived",
    },
    {
        key: "combatEvents",
        label: "Combat events",
        detail: "Current-turn VCR contacts and combat markers",
        provenance: "facts",
    },
    {
        key: "hostEvents",
        label: "Host events",
        detail: "Observed host/explosion event markers",
        provenance: "facts",
    },
    {
        key: "spatialMessages",
        label: "Spatial messages",
        detail: "Coordinate-bearing messages from the selected observer",
        provenance: "private facts",
    },
];


export function MapLayerControls({
    visibility,
    onChange,
    available,
}: {
    visibility: MapLayerVisibility;
    onChange: (next: MapLayerVisibility) => void;
    available?: readonly (keyof MapLayerVisibility)[];
}) {
    const [open, setOpen] = useState(false);
    const visibleLayers = available === undefined
        ? LAYERS
        : LAYERS.filter(({ key }) => available.includes(key));
    const enabledCount = visibleLayers.filter(({ key }) => visibility[key]).length;

    function toggle(key: MapLayerKey) {
        onChange({
            ...visibility,
            [key]: !visibility[key],
        });
    }

    function setAll(value: boolean) {
        onChange({
            ...visibility,
            ...Object.fromEntries(visibleLayers.map(({ key }) => [key, value])),
        } as MapLayerVisibility);
    }

    return (
        <div className="map-layer-controls-shell">
            <button
                aria-expanded={open}
                className={
                    "map-layer-controls-toggle"
                    + (open ? " is-open" : "")
                }
                onClick={() => setOpen((value) => !value)}
                type="button"
            >
                <strong>Layers</strong>
                <span>{enabledCount}/{visibleLayers.length} visible</span>
            </button>

            {open && (
                <div
                    aria-label="Map layer visibility"
                    className="map-layer-controls-panel"
                    role="group"
                >
                    <div className="map-layer-controls-heading">
                        <div>
                            <strong>Map layers</strong>
                            <span>Visibility changes presentation only.</span>
                        </div>
                        <div className="map-layer-controls-quick">
                            <button onClick={() => setAll(true)} type="button">
                                All on
                            </button>
                            <button onClick={() => setAll(false)} type="button">
                                All off
                            </button>
                        </div>
                    </div>

                    <div className="map-layer-controls-list">
                        {visibleLayers.map((layer) => (
                            <button
                                aria-pressed={visibility[layer.key]}
                                className={
                                    "map-layer-control"
                                    + (visibility[layer.key] ? " is-active" : "")
                                }
                                key={layer.key}
                                onClick={() => toggle(layer.key)}
                                type="button"
                            >
                                <span
                                    aria-hidden="true"
                                    className="map-layer-control-indicator"
                                />
                                <span className="map-layer-control-copy">
                                    <span className="map-layer-control-title">
                                        <strong>{layer.label}</strong>
                                        <em>{layer.provenance}</em>
                                    </span>
                                    <small>{layer.detail}</small>
                                </span>
                            </button>
                        ))}
                    </div>

                    <p className="map-layer-controls-note">
                        Hiding a layer never changes stored evidence, drafts or
                        historical snapshots.
                    </p>
                </div>
            )}
        </div>
    );
}
