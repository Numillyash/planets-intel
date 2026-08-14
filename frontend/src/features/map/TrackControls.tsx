import { useState } from "react";

import type { ShipTrackMode } from "./historicalTrackScene";
import "./track-controls.css";


export function TrackControls({
    mode,
    lookbackTurns,
    fadePercent,
    onModeChange,
    onLookbackChange,
    onFadeChange,
}: {
    mode: ShipTrackMode;
    lookbackTurns: number | null;
    fadePercent: number;
    onModeChange: (mode: ShipTrackMode) => void;
    onLookbackChange: (turns: number | null) => void;
    onFadeChange: (percent: number) => void;
}) {
    const [open, setOpen] = useState(false);
    const lookbackLabel = lookbackTurns === null ? "All" : `${lookbackTurns}T`;

    return (
        <div className="track-controls-shell">
            <button
                className={
                    "track-controls-toggle"
                    + (open ? " is-open" : "")
                }
                onClick={() => setOpen((value) => !value)}
                type="button"
            >
                <strong>Tracks</strong>
                <span>{mode} · {lookbackLabel}</span>
            </button>

            {open && (
                <div className="track-controls-panel">
                    <div className="track-controls-heading">
                        <strong>Historical tracks</strong>
                        <span>Direction uses only contiguous factual evidence.</span>
                    </div>

                    <div className="track-controls-group">
                        <span className="track-controls-label">Visible</span>
                        <div className="track-controls-segmented">
                            {(["off", "selected", "all"] as ShipTrackMode[]).map((value) => (
                                <button
                                    className={mode === value ? "is-active" : ""}
                                    key={value}
                                    onClick={() => onModeChange(value)}
                                    type="button"
                                >
                                    {value === "off"
                                        ? "Off"
                                        : value === "selected"
                                            ? "Selected"
                                            : "All"}
                                </button>
                            ))}
                        </div>
                    </div>

                    <label className="track-controls-field">
                        <span>History depth</span>
                        <select
                            onChange={(event) => {
                                const value = event.target.value;
                                onLookbackChange(
                                    value === "all" ? null : Number(value),
                                );
                            }}
                            value={lookbackTurns === null ? "all" : String(lookbackTurns)}
                        >
                            <option value="1">1 turn</option>
                            <option value="3">3 turns</option>
                            <option value="5">5 turns</option>
                            <option value="10">10 turns</option>
                            <option value="20">20 turns</option>
                            <option value="all">All stored</option>
                        </select>
                    </label>

                    <label className="track-controls-field">
                        <span>Fade per turn · {fadePercent}%</span>
                        <input
                            max={50}
                            min={0}
                            onChange={(event) => onFadeChange(Number(event.target.value))}
                            step={5}
                            type="range"
                            value={fadePercent}
                        />
                    </label>
                </div>
            )}
        </div>
    );
}
