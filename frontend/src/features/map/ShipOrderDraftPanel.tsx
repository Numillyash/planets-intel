import { useEffect, useMemo, useState } from "react";

import { getCombinedPrivateIntel } from "../../api/client";
import {
    discardShipOrderDraft,
    getShipOrderDraft,
    saveShipOrderDraft,
} from "../../api/orderDraft";
import type {
    ShipDraftMovementMode,
    ShipOrderDraft,
} from "../../types/orderDraft";
import "./order-draft.css";


interface WaypointPickedDetail {
    shipId: number;
    x: number;
    y: number;
}


interface InterceptCandidate {
    shipId: number;
    name: string | null;
    x: number;
    y: number;
}


function waypointLabel(x: number | null, y: number | null): string {
    return x !== null && y !== null ? `${x}, ${y}` : "—";
}


function candidateLabel(candidate: InterceptCandidate): string {
    return `${candidate.name ?? `Ship #${candidate.shipId}`} (#${candidate.shipId})`;
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
    const [movementMode, setMovementMode] =
        useState<ShipDraftMovementMode>("waypoint");
    const [interceptTargetShipId, setInterceptTargetShipId] =
        useState<number | null>(null);
    const [interceptCandidates, setInterceptCandidates] =
        useState<InterceptCandidate[]>([]);
    const [ambiguousTargets, setAmbiguousTargets] =
        useState<InterceptCandidate[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [pickingWaypoint, setPickingWaypoint] = useState(false);
    const [pickingInterceptTarget, setPickingInterceptTarget] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        setInterceptCandidates([]);
        setAmbiguousTargets([]);

        void getShipOrderDraft(gameId, linkedAccountId, turn, shipId)
            .then((value) => {
                if (cancelled) return;
                setDraft(value);
                setWarp(value?.warp ?? upstreamWarp ?? 0);
                setWaypointX(value?.waypoint_x ?? upstreamWaypointX);
                setWaypointY(value?.waypoint_y ?? upstreamWaypointY);
                setMovementMode(value?.movement_mode ?? "waypoint");
                setInterceptTargetShipId(value?.intercept_target_ship_id ?? null);
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

            if (!pickingInterceptTarget) {
                setWaypointX(detail.x);
                setWaypointY(detail.y);
                setPickingWaypoint(false);
                return;
            }

            const nearby = interceptCandidates
                .map((candidate) => ({
                    candidate,
                    distance: Math.hypot(
                        candidate.x - detail.x,
                        candidate.y - detail.y,
                    ),
                }))
                .filter((entry) => entry.distance <= 24)
                .sort((left, right) =>
                    left.distance - right.distance
                    || left.candidate.shipId - right.candidate.shipId,
                );

            setPickingInterceptTarget(false);

            if (nearby.length === 0) {
                setAmbiguousTargets([]);
                setError(
                    "No visible ship was found near that map click. Pick the hull marker rather than empty space.",
                );
                return;
            }

            const bestDistance = nearby[0].distance;
            const plausible = nearby
                .filter((entry) => entry.distance <= bestDistance + 2.5)
                .map((entry) => entry.candidate);

            if (plausible.length === 1) {
                setInterceptTargetShipId(plausible[0].shipId);
                setAmbiguousTargets([]);
                setError(null);
                return;
            }

            setAmbiguousTargets(plausible);
            setError(null);
        };

        const handleWaypointCancelled = (event: Event) => {
            const detail = (event as CustomEvent<{ shipId: number }>).detail;
            if (detail?.shipId !== shipId) return;
            setPickingWaypoint(false);
            setPickingInterceptTarget(false);
        };

        window.addEventListener("intel-waypoint-picked", handleWaypoint);
        window.addEventListener("intel-waypoint-pick-cancelled", handleWaypointCancelled);
        return () => {
            window.removeEventListener("intel-waypoint-picked", handleWaypoint);
            window.removeEventListener("intel-waypoint-pick-cancelled", handleWaypointCancelled);
        };
    }, [interceptCandidates, pickingInterceptTarget, shipId]);

    useEffect(() => {
        return () => {
            window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
                detail: { shipId },
            }));
        };
    }, [shipId]);

    const changed = useMemo(() => {
        const savedWarp = draft?.warp ?? upstreamWarp ?? 0;
        const savedWaypointX = draft?.waypoint_x ?? upstreamWaypointX;
        const savedWaypointY = draft?.waypoint_y ?? upstreamWaypointY;
        const savedMode = draft?.movement_mode ?? "waypoint";
        const savedTarget = draft?.intercept_target_ship_id ?? null;

        return warp !== savedWarp
            || waypointX !== savedWaypointX
            || waypointY !== savedWaypointY
            || movementMode !== savedMode
            || interceptTargetShipId !== savedTarget;
    }, [
        draft,
        interceptTargetShipId,
        movementMode,
        upstreamWarp,
        upstreamWaypointX,
        upstreamWaypointY,
        warp,
        waypointX,
        waypointY,
    ]);

    const canSave = changed
        && (movementMode !== "intercept" || interceptTargetShipId !== null);

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

    function cancelMapPicker() {
        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
            detail: { shipId },
        }));
        setPickingWaypoint(false);
        setPickingInterceptTarget(false);
    }

    function changeMovementMode(nextMode: ShipDraftMovementMode) {
        cancelMapPicker();
        setAmbiguousTargets([]);
        setMovementMode(nextMode);
        if (nextMode === "waypoint") {
            setInterceptTargetShipId(null);
        }
    }

    function toggleWaypointPicker() {
        if (pickingWaypoint) {
            cancelMapPicker();
            return;
        }
        cancelMapPicker();
        setAmbiguousTargets([]);
        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-start", {
            detail: { shipId },
        }));
        setPickingWaypoint(true);
    }

    async function toggleInterceptPicker() {
        if (pickingInterceptTarget) {
            cancelMapPicker();
            return;
        }

        cancelMapPicker();
        setError(null);
        setAmbiguousTargets([]);

        let candidates = interceptCandidates;
        if (candidates.length === 0) {
            try {
                const intel = await getCombinedPrivateIntel(gameId, linkedAccountId);
                candidates = (intel?.ships ?? [])
                    .filter((ship) =>
                        ship.ship_id !== shipId
                        && ship.x !== null
                        && ship.y !== null,
                    )
                    .map((ship) => ({
                        shipId: ship.ship_id,
                        name: ship.name,
                        x: ship.x as number,
                        y: ship.y as number,
                    }));
                setInterceptCandidates(candidates);
            } catch (reason) {
                setError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load visible intercept targets",
                );
                return;
            }
        }

        if (candidates.length === 0) {
            setError("No visible target ships are available in this snapshot.");
            return;
        }

        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-start", {
            detail: { shipId },
        }));
        setPickingInterceptTarget(true);
    }

    async function saveDraft() {
        if (!canSave) return;
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
                    movement_mode: movementMode,
                    ...(movementMode === "intercept"
                        ? {
                            intercept_target_ship_id: interceptTargetShipId ?? undefined,
                        }
                        : waypointX !== null && waypointY !== null
                            ? {
                                waypoint_x: waypointX,
                                waypoint_y: waypointY,
                            }
                            : {}),
                },
            );
            setDraft(next);
            setMovementMode(next.movement_mode);
            setInterceptTargetShipId(next.intercept_target_ship_id);
            setAmbiguousTargets([]);
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
            setMovementMode("waypoint");
            setInterceptTargetShipId(null);
            setAmbiguousTargets([]);
            cancelMapPicker();
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
                    <strong>Movement</strong>
                    <span>Nu mission unchanged</span>
                    <select
                        aria-label="Draft movement mode"
                        disabled={saving}
                        onChange={(event) => changeMovementMode(
                            event.target.value as ShipDraftMovementMode,
                        )}
                        value={movementMode}
                    >
                        <option value="waypoint">Waypoint</option>
                        <option value="intercept">Intercept</option>
                    </select>
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

                {movementMode === "waypoint" ? (
                    <div className="order-draft-row">
                        <strong>Waypoint</strong>
                        <span>{waypointLabel(upstreamWaypointX, upstreamWaypointY)}</span>
                        <span className="order-draft-waypoint-value">
                            {waypointLabel(waypointX, waypointY)}
                        </span>
                    </div>
                ) : (
                    <div className="order-draft-row">
                        <strong>Target</strong>
                        <span>Visible ship required</span>
                        <span className="order-draft-waypoint-value">
                            {interceptTargetShipId !== null
                                ? `Ship #${interceptTargetShipId}`
                                : "—"}
                        </span>
                    </div>
                )}
            </div>

            {ambiguousTargets.length > 1 && (
                <div className="order-draft-target-choice">
                    <strong>Several ships are stacked near that click</strong>
                    <span>Select the intended Intercept target:</span>
                    <select
                        aria-label="Intercept target candidate"
                        defaultValue=""
                        onChange={(event) => {
                            const targetId = Number(event.target.value);
                            if (!Number.isFinite(targetId) || targetId <= 0) return;
                            setInterceptTargetShipId(targetId);
                            setAmbiguousTargets([]);
                        }}
                    >
                        <option disabled value="">Choose ship…</option>
                        {ambiguousTargets.map((candidate) => (
                            <option key={candidate.shipId} value={candidate.shipId}>
                                {candidateLabel(candidate)}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            <div className="order-draft-actions">
                {movementMode === "waypoint" ? (
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
                ) : (
                    <button
                        className={
                            "secondary-button"
                            + (pickingInterceptTarget ? " is-active" : "")
                        }
                        disabled={saving}
                        onClick={() => void toggleInterceptPicker()}
                        type="button"
                    >
                        {pickingInterceptTarget
                            ? "Cancel target pick"
                            : interceptTargetShipId === null
                                ? "Pick intercept target"
                                : "Change intercept target"}
                    </button>
                )}

                <button
                    className="primary-button"
                    disabled={saving || !canSave}
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

            {pickingInterceptTarget && (
                <p className="order-draft-map-hint">
                    Click the visible target ship on the Starmap. Dense stacks will ask you to choose the exact ship.
                </p>
            )}

            {movementMode === "intercept" && interceptTargetShipId !== null && (
                <p className="order-draft-provenance">
                    Intercept target lock: Ship #{interceptTargetShipId}. The persistent map vector points to the factual target sighting; post-Move-Most prediction belongs to the next movement-simulator layer.
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
