import { useEffect, useMemo, useState } from "react";

import { getCombinedPrivateIntel } from "../../api/client";
import {
    discardShipOrderDraft,
    getShipOrderDraft,
    saveShipOrderDraft,
} from "../../api/orderDraft";
import type { PlayerInfo } from "../../types/api";
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

const COMMON_MISSIONS = [
    "Exploration",
    "Mine Sweep",
    "Lay Mines",
    "Kill!",
    "Sensor Sweep",
    "Land and Disassemble",
    "Try to Tow",
    "Intercept",
    "Enter Wormhole",
    "Load Artifact",
    "Transfer Artifact",
    "Beam Up",
];

function waypointLabel(x: number | null, y: number | null): string {
    return x !== null && y !== null ? `${x}, ${y}` : "—";
}

function candidateLabel(candidate: InterceptCandidate): string {
    return `${candidate.name ?? `Ship #${candidate.shipId}`} (#${candidate.shipId})`;
}

function isInterceptMission(value: string): boolean {
    return value.trim().toLowerCase() === "intercept";
}

export function ShipOrderDraftPanel({
    gameId,
    linkedAccountId,
    turn,
    shipId,
    upstreamWarp,
    upstreamWaypointX,
    upstreamWaypointY,
    upstreamFriendlyCode,
    upstreamMission,
    upstreamPrimaryEnemyId,
    players,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    shipId: number;
    upstreamWarp: number | null;
    upstreamWaypointX: number | null;
    upstreamWaypointY: number | null;
    upstreamFriendlyCode: string | null;
    upstreamMission: string | null;
    upstreamPrimaryEnemyId: number | null;
    players: PlayerInfo[];
}) {
    const [draft, setDraft] = useState<ShipOrderDraft | null>(null);
    const [warp, setWarp] = useState<number>(upstreamWarp ?? 0);
    const [waypointX, setWaypointX] = useState<number | null>(upstreamWaypointX);
    const [waypointY, setWaypointY] = useState<number | null>(upstreamWaypointY);
    const [movementMode, setMovementMode] =
        useState<ShipDraftMovementMode>("waypoint");
    const [interceptTargetShipId, setInterceptTargetShipId] =
        useState<number | null>(null);
    const [friendlyCode, setFriendlyCode] = useState(upstreamFriendlyCode ?? "");
    const [mission, setMission] = useState(upstreamMission ?? "Exploration");
    const [primaryEnemyId, setPrimaryEnemyId] = useState(upstreamPrimaryEnemyId ?? 0);
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
                setFriendlyCode(value?.friendly_code ?? upstreamFriendlyCode ?? "");
                setMission(
                    value?.mission
                    ?? (value?.movement_mode === "intercept" ? "Intercept" : null)
                    ?? upstreamMission
                    ?? "Exploration",
                );
                setPrimaryEnemyId(
                    value?.primary_enemy_id ?? upstreamPrimaryEnemyId ?? 0,
                );
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
        upstreamFriendlyCode,
        upstreamMission,
        upstreamPrimaryEnemyId,
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
                setError("No visible ship was found near that map click.");
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

    useEffect(() => () => {
        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
            detail: { shipId },
        }));
    }, [shipId]);

    const changed = useMemo(() => {
        const savedWarp = draft?.warp ?? upstreamWarp ?? 0;
        const savedWaypointX = draft?.waypoint_x ?? upstreamWaypointX;
        const savedWaypointY = draft?.waypoint_y ?? upstreamWaypointY;
        const savedMode = draft?.movement_mode ?? "waypoint";
        const savedTarget = draft?.intercept_target_ship_id ?? null;
        const savedCode = draft?.friendly_code ?? upstreamFriendlyCode ?? "";
        const savedMission = draft?.mission
            ?? (savedMode === "intercept" ? "Intercept" : upstreamMission ?? "Exploration");
        const savedEnemy = draft?.primary_enemy_id ?? upstreamPrimaryEnemyId ?? 0;

        return warp !== savedWarp
            || waypointX !== savedWaypointX
            || waypointY !== savedWaypointY
            || movementMode !== savedMode
            || interceptTargetShipId !== savedTarget
            || friendlyCode !== savedCode
            || mission !== savedMission
            || primaryEnemyId !== savedEnemy;
    }, [
        draft,
        friendlyCode,
        interceptTargetShipId,
        mission,
        movementMode,
        primaryEnemyId,
        upstreamFriendlyCode,
        upstreamMission,
        upstreamPrimaryEnemyId,
        upstreamWarp,
        upstreamWaypointX,
        upstreamWaypointY,
        warp,
        waypointX,
        waypointY,
    ]);

    const canSave = changed
        && mission.trim().length > 0
        && friendlyCode.length <= 3
        && (movementMode !== "intercept" || interceptTargetShipId !== null);

    function announceDraftChange(action: "saved" | "discarded") {
        window.dispatchEvent(new CustomEvent("intel-order-drafts-changed", {
            detail: { action, gameId, linkedAccountId, turn, shipId },
        }));
    }

    function cancelMapPicker() {
        window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancel", {
            detail: { shipId },
        }));
        setPickingWaypoint(false);
        setPickingInterceptTarget(false);
    }

    function changeMission(nextMission: string) {
        setMission(nextMission);
        cancelMapPicker();
        setAmbiguousTargets([]);
        if (isInterceptMission(nextMission)) {
            setMovementMode("intercept");
        } else {
            setMovementMode("waypoint");
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
                setError(reason instanceof Error ? reason.message : "Failed to load targets");
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
                    friendly_code: friendlyCode,
                    mission: mission.trim(),
                    primary_enemy_id: primaryEnemyId,
                    ...(movementMode === "intercept"
                        ? { intercept_target_ship_id: interceptTargetShipId ?? undefined }
                        : waypointX !== null && waypointY !== null
                            ? { waypoint_x: waypointX, waypoint_y: waypointY }
                            : {}),
                },
            );
            setDraft(next);
            setMovementMode(next.movement_mode);
            setInterceptTargetShipId(next.intercept_target_ship_id);
            setFriendlyCode(next.friendly_code ?? friendlyCode);
            setMission(next.mission ?? mission);
            setPrimaryEnemyId(next.primary_enemy_id ?? primaryEnemyId);
            setAmbiguousTargets([]);
            announceDraftChange("saved");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to save local order draft");
        } finally {
            setSaving(false);
        }
    }

    async function discardDraft() {
        setSaving(true);
        setError(null);
        try {
            await discardShipOrderDraft(gameId, linkedAccountId, turn, shipId);
            setDraft(null);
            setWarp(upstreamWarp ?? 0);
            setWaypointX(upstreamWaypointX);
            setWaypointY(upstreamWaypointY);
            setMovementMode("waypoint");
            setInterceptTargetShipId(null);
            setFriendlyCode(upstreamFriendlyCode ?? "");
            setMission(upstreamMission ?? "Exploration");
            setPrimaryEnemyId(upstreamPrimaryEnemyId ?? 0);
            setAmbiguousTargets([]);
            cancelMapPicker();
            announceDraftChange("discarded");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to discard local order draft");
        } finally {
            setSaving(false);
        }
    }

    if (loading) return <p className="intel-no-facts">Loading local order draft…</p>;

    return (
        <div className="order-draft-panel">
            <datalist id={`ship-missions-${shipId}`}>
                {COMMON_MISSIONS.map((value) => <option key={value} value={value} />)}
            </datalist>

            <div className="operational-intel-callout order-draft-callout">
                <strong>{draft !== null ? "Local draft orders" : "Plan this ship"}</strong>
                <span>Changes are stored only in Planets Intel. Nothing is sent to Planets.nu yet.</span>
            </div>

            {draft?.stale && <div className="order-draft-warning">The factual snapshot changed after this draft was saved. Review it.</div>}
            {error !== null && <div className="order-draft-error">{error}</div>}

            <div className="order-draft-comparison">
                <div className="order-draft-row order-draft-row-heading">
                    <span>Order</span><span>Upstream</span><span>Draft</span>
                </div>

                <div className="order-draft-row">
                    <strong>Mission</strong>
                    <span>{upstreamMission ?? "—"}</span>
                    <input
                        aria-label="Draft mission"
                        disabled={saving}
                        list={`ship-missions-${shipId}`}
                        maxLength={80}
                        onChange={(event) => changeMission(event.target.value)}
                        value={mission}
                    />
                </div>

                <div className="order-draft-row">
                    <strong>Primary enemy</strong>
                    <span>{upstreamPrimaryEnemyId && upstreamPrimaryEnemyId > 0 ? `Player ${upstreamPrimaryEnemyId}` : "None"}</span>
                    <select
                        aria-label="Draft primary enemy"
                        disabled={saving}
                        onChange={(event) => setPrimaryEnemyId(Number(event.target.value))}
                        value={primaryEnemyId}
                    >
                        <option value={0}>None</option>
                        {players
                            .filter((player) => player.slot_id > 0)
                            .sort((a, b) => a.slot_id - b.slot_id)
                            .map((player) => (
                                <option key={player.slot_id} value={player.slot_id}>
                                    {player.slot_id}: {player.username}
                                </option>
                            ))}
                    </select>
                </div>

                <div className="order-draft-row">
                    <strong>Friendly code</strong>
                    <span>{upstreamFriendlyCode ?? "—"}</span>
                    <input
                        aria-label="Draft friendly code"
                        disabled={saving}
                        maxLength={3}
                        onChange={(event) => setFriendlyCode(event.target.value)}
                        value={friendlyCode}
                    />
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
                            <option key={value} value={value}>Warp {value}</option>
                        ))}
                    </select>
                </div>

                {movementMode === "waypoint" ? (
                    <div className="order-draft-row">
                        <strong>Waypoint</strong>
                        <span>{waypointLabel(upstreamWaypointX, upstreamWaypointY)}</span>
                        <span className="order-draft-waypoint-value">{waypointLabel(waypointX, waypointY)}</span>
                    </div>
                ) : (
                    <div className="order-draft-row">
                        <strong>Intercept target</strong>
                        <span>Visible ship required</span>
                        <span className="order-draft-waypoint-value">
                            {interceptTargetShipId !== null ? `Ship #${interceptTargetShipId}` : "—"}
                        </span>
                    </div>
                )}
            </div>

            {ambiguousTargets.length > 1 && (
                <div className="order-draft-target-choice">
                    <strong>Several ships are stacked near that click</strong>
                    <select
                        aria-label="Intercept target candidate"
                        defaultValue=""
                        onChange={(event) => {
                            const targetId = Number(event.target.value);
                            if (Number.isFinite(targetId) && targetId > 0) {
                                setInterceptTargetShipId(targetId);
                                setAmbiguousTargets([]);
                            }
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
                    <button className={`secondary-button${pickingWaypoint ? " is-active" : ""}`} disabled={saving} onClick={toggleWaypointPicker} type="button">
                        {pickingWaypoint ? "Cancel waypoint pick" : "Pick waypoint on map"}
                    </button>
                ) : (
                    <button className={`secondary-button${pickingInterceptTarget ? " is-active" : ""}`} disabled={saving} onClick={() => void toggleInterceptPicker()} type="button">
                        {pickingInterceptTarget ? "Cancel target pick" : interceptTargetShipId === null ? "Pick intercept target" : "Change intercept target"}
                    </button>
                )}

                <button className="primary-button" disabled={saving || !canSave} onClick={() => void saveDraft()} type="button">
                    {saving ? "Saving…" : "Save draft"}
                </button>
                {draft !== null && (
                    <button className="secondary-button" disabled={saving} onClick={() => void discardDraft()} type="button">
                        Discard draft
                    </button>
                )}
            </div>

            {pickingWaypoint && <p className="order-draft-map-hint">Click a destination on the Starmap. Dragging still pans the map.</p>}
            {pickingInterceptTarget && <p className="order-draft-map-hint">Click the visible target ship on the Starmap.</p>}

            <p className="order-draft-provenance">
                Common missions are suggested, but special race/hull missions may be typed by their Nu display name. Numeric write-back mapping is deliberately deferred until the Planets.nu write API is verified.
            </p>
            {draft !== null && <p className="order-draft-provenance">Draft based on factual batch #{draft.base_batch_id}. It remains separate from canonical observations.</p>}
        </div>
    );
}
