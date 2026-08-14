import { useEffect, useMemo, useState } from "react";

import {
    discardShipOrderDraft,
    getShipOrderDraft,
    saveShipOrderDraft,
} from "../../api/orderDraft";
import type { ShipOrderDraft } from "../../types/orderDraft";
import "./order-draft.css";


interface WaypointPickedDetail {
    shipId: number;
    x: number;
    y: number;
}


function waypointLabel(x: number | null, y: number | null): string {
    return x !== null && y !== null ? `${x}, ${y}` : "—";
}


export function ShipOrderDraftPanel({
    gameId,
    linkedAccountId,
    turn,
    shipId,
    upstreamWarp,
    upstreamWaypointX,
    upstreamWaypointY,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    shipId: number;
    upstreamWarp: number | null;
    upstreamWaypointX: number | null;
    upstreamWaypointY: number | null;
}) {
    const [draft, setDraft] = useState<ShipOrderDraft | null>(null);
    const [warp, setWarp] = useState<number>(upstreamWarp ?? 0);
    const [waypointX, setWaypointX] = useState<number | null>(upstreamWaypointX);
    const [waypointY, setWaypointY] = useState<number | null>(upstreamWaypointY);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [pickingWaypoint, setPickingWaypoint] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        void getShipOrderDraft(gameId, linkedAccountId, turn, shipId)
            .then((value) => {
                if (cancelled) return;
                setDraft(value);
                setWarp(value?.warp ?? upstreamWarp ?? 0);
                setWaypointX(value?.waypoint_x ?? upstreamWaypointX);
                setWaypointY(value?.waypoint_y ?? upstreamWaypointY);
            })
            .catch((reason) => {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load local order draft",
                    );
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [
        gameId,
        linkedAccountId,
        shipId,
        turn,
        upstreamWarp,
        upstreamWaypointX,
        upstreamWaypointY,
    ]);

    useEffect(() => {
        const handleWaypoint = (event: Event) => {
            const detail = (event as CustomEvent<WaypointPickedDetail>).detail;
            if (!detail || detail.shipId !== shipId) return;
            setWaypointX(detail.x);
            setWaypointY(detail.y);
            setPickingWaypoint(false);
        };
        const handleCancelled = (event: Event) => {
            const detail = (event as CustomEvent<{ shipId: number }>).detail;
            if (detail?.shipId === shipId) setPickingWaypoint(false);
        };

        window.addEventListener("intel-waypoint-picked", handleWaypoint);
        window.addEventListener("intel-waypoint-pick-cancelled", handleCancelled);
        return () => {
            window.removeEventListener("intel-waypoint-picked", handleWaypoint);
            window.removeEventListener("intel-waypoint-pick-cancelled", handleCancelled);
        };
    }, [shipId]);

    useEffect(() => {
        return () => {
            window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
                detail: { shipId },
            }));
        };
    }, [shipId]);

    const changed = useMemo(() => {
        return warp !== (upstreamWarp ?? 0)
            || waypointX !== upstreamWaypointX
            || waypointY !== upstreamWaypointY;
    }, [
        upstreamWarp,
        upstreamWaypointX,
        upstreamWaypointY,
        warp,
        waypointX,
        waypointY,
    ]);

    function announceDraftChange(action: "saved" | "discarded") {
        window.dispatchEvent(new CustomEvent("intel-order-drafts-changed", {
            detail: {
                action,
                gameId,
                linkedAccountId,
                turn,
                shipId,
            },
        }));
    }

    function toggleWaypointPicker() {
        if (pickingWaypoint) {
            window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
                detail: { shipId },
            }));
            setPickingWaypoint(false);
            return;
        }
        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-start", {
            detail: { shipId },
        }));
        setPickingWaypoint(true);
    }

    async function saveDraft() {
        setSaving(true);
        setError(null);
        try {
            const next = await saveShipOrderDraft(
                gameId,
                linkedAccountId,
                turn,
                shipId,
                {
                    warp,
                    ...(waypointX !== null && waypointY !== null
                        ? {
                            waypoint_x: waypointX,
                            waypoint_y: waypointY,
                        }
                        : {}),
                },
            );
            setDraft(next);
            announceDraftChange("saved");
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to save local order draft",
            );
        } finally {
            setSaving(false);
        }
    }

    async function discardDraft() {
        setSaving(true);
        setError(null);
        try {
            await discardShipOrderDraft(
                gameId,
                linkedAccountId,
                turn,
                shipId,
            );
            setDraft(null);
            setWarp(upstreamWarp ?? 0);
            setWaypointX(upstreamWaypointX);
            setWaypointY(upstreamWaypointY);
            announceDraftChange("discarded");
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to discard local order draft",
            );
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="intel-no-facts">Loading local order draft…</p>;
    }

    return (
        <div className="order-draft-panel">
            <div className="operational-intel-callout order-draft-callout">
                <strong>
                    {draft !== null ? "Local draft orders" : "Plan this ship"}
                </strong>
                <span>
                    Changes are stored only in Planets Intel. Nothing is sent to Planets.nu yet.
                </span>
            </div>

            {draft?.stale && (
                <div className="order-draft-warning">
                    The factual snapshot changed after this draft was saved. Review the draft before relying on it.
                </div>
            )}

            {error !== null && (
                <div className="order-draft-error">{error}</div>
            )}

            <div className="order-draft-comparison">
                <div className="order-draft-row order-draft-row-heading">
                    <span>Order</span>
                    <span>Upstream</span>
                    <span>Draft</span>
                </div>

                <div className="order-draft-row">
                    <strong>Warp</strong>
                    <span>{upstreamWarp ?? "—"}</span>
                    <select
                        aria-label="Draft warp"
                        disabled={saving}
                        onChange={(event) => setWarp(Number(event.target.value))}
                        value={warp}
                    >
                        {Array.from({ length: 10 }, (_, value) => (
                            <option key={value} value={value}>
                                Warp {value}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="order-draft-row">
                    <strong>Waypoint</strong>
                    <span>{waypointLabel(upstreamWaypointX, upstreamWaypointY)}</span>
                    <span className="order-draft-waypoint-value">
                        {waypointLabel(waypointX, waypointY)}
                    </span>
                </div>
            </div>

            <div className="order-draft-actions">
                <button
                    className={
                        "secondary-button"
                        + (pickingWaypoint ? " is-active" : "")
                    }
                    disabled={saving}
                    onClick={toggleWaypointPicker}
                    type="button"
                >
                    {pickingWaypoint ? "Cancel waypoint pick" : "Pick waypoint on map"}
                </button>
                <button
                    className="primary-button"
                    disabled={saving || !changed}
                    onClick={() => void saveDraft()}
                    type="button"
                >
                    {saving ? "Saving…" : "Save draft"}
                </button>
                {draft !== null && (
                    <button
                        className="secondary-button"
                        disabled={saving}
                        onClick={() => void discardDraft()}
                        type="button"
                    >
                        Discard draft
                    </button>
                )}
            </div>

            {pickingWaypoint && (
                <p className="order-draft-map-hint">
                    Click a destination on the Starmap. Dragging still pans the map; a short click selects the waypoint.
                </p>
            )}

            {draft !== null && (
                <p className="order-draft-provenance">
                    Draft based on factual batch #{draft.base_batch_id}. It remains separate from canonical observations.
                </p>
            )}
        </div>
    );
}
