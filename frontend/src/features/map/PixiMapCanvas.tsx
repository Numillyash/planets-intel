import {
    type MutableRefObject,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import { Application, Assets, Container, Graphics, Text } from "pixi.js";
import { getHostEvents } from "../../api/activity";
import { getHistoricalShipTracks } from "../../api/history";
import { privateHullAssetUrl } from "../../lib/privateAssets";
import type { HostEventItem } from "../../types/activity";
import type {
    CombatEventSummary,
    HistoricalCombatEvent,
    HistoricalCombatEventSide,
    HistoricalCombatOutcome,
    HistoricalShipTrack,
} from "../../types/history";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import {
    observedBounds,
    planetLinks,
    renderY,
    shipVisualPositions,
    starbaseByPlanetId,
    type MapBounds,
    type PlanetLabelMode,
    type SelectedEntity,
} from "./mapModel";
import {
    ionStormAtPoint,
    radiationAtPoint,
} from "./navigationAnalysis";
import { CombatEventPanel } from "./CombatEventPanel";
import { drawHostEvents, hostEventKey } from "./hostEventScene";
import { drawMapScene } from "./mapScene";
import { drawOrderVectors } from "./orderVectorScene";
import {
    clearCurrentCombatContacts,
    combatEventKey,
    drawCurrentCombatContacts,
    drawHistoricalShipTracks,
    type ShipTrackMode,
} from "./historicalTrackScene";
import { drawMinefields } from "./minefieldScene";
import {
    DEFAULT_MAP_LAYER_VISIBILITY,
    MapLayerControls,
    type MapLayerVisibility,
} from "./MapLayerControls";
import { TrackControls } from "./TrackControls";
import { useMapOrderDrafts } from "./useMapOrderDrafts";


function combatOutcomeLabel(outcome: HistoricalCombatOutcome | null): string {
    switch (outcome) {
        case "defeated":
            return "Defeated in this combat";
        case "survived_to_later_combat":
            return "Survived to a later combat at this position";
        default:
            return "Final result not proven by VCR sequence";
    }
}


function combatSideName(side: HistoricalCombatEventSide): string {
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}


function combatEventKind(event: HistoricalCombatEvent): string {
    const ships = event.sides.filter((side) => side.object_kind === "ship").length;
    if (ships === 2) return "Ship combat";
    if (ships === 1) return "Planet combat";
    return "Combat";
}


async function warmHullTexture(url: string): Promise<void> {
    let lastError: unknown = null;

    for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                cache: "force-cache",
                headers: { Accept: "image/png" },
            });
            if (!response.ok) {
                throw new Error(`Hull asset HTTP ${response.status}`);
            }
            await response.blob();
            await Assets.load(url);
            return;
        } catch (reason) {
            lastError = reason;
            if (attempt < 3) {
                await new Promise((resolve) => {
                    window.setTimeout(resolve, attempt * 650);
                });
            }
        }
    }

    throw lastError;
}


export function PixiMapCanvas({
    intel,
    labelMode,
    selected,
    onSelect,
    fitViewRef,
}: {
    intel: PrivateIntelMapResponse;
    labelMode: PlanetLabelMode;
    selected: SelectedEntity | null;
    onSelect: (entity: SelectedEntity) => void;
    fitViewRef: MutableRefObject<(() => void) | null>;
}) {
    const hostRef = useRef<HTMLDivElement>(null);
    const appRef = useRef<Application | null>(null);
    const worldRef = useRef<Container | null>(null);
    const hoverLayerRef = useRef<Container | null>(null);
    const hoverBackgroundRef = useRef<Graphics | null>(null);
    const hoverTextRef = useRef<Text | null>(null);
    const intelRef = useRef(intel);
    const boundsRef = useRef<MapBounds | null>(null);
    const lastFitGameIdRef = useRef<number | null>(null);
    const waypointPickShipIdRef = useRef<number | null>(null);
    const loadedHullAssetUrlsRef = useRef<Set<string>>(new Set());
    const loadingHullAssetUrlsRef = useRef<Set<string>>(new Set());
    const [appReadyRevision, setAppReadyRevision] = useState(0);
    const [hullArtworkRevision, setHullArtworkRevision] = useState(0);
    const [waypointPickShipId, setWaypointPickShipId] = useState<number | null>(null);
    const [historicalTracks, setHistoricalTracks] =
        useState<HistoricalShipTrack[]>([]);
    const [trackMode, setTrackMode] = useState<ShipTrackMode>("all");
    const [trackLookbackTurns, setTrackLookbackTurns] =
        useState<number | null>(5);
    const [trackFadePercent, setTrackFadePercent] = useState(20);
    const [selectedCombatEvent, setSelectedCombatEvent] =
        useState<HistoricalCombatEvent | null>(null);
    const [hostEvents, setHostEvents] = useState<HostEventItem[]>([]);
    const [selectedHostEventKey, setSelectedHostEventKey] =
        useState<string | null>(null);
    const [layerVisibility, setLayerVisibility] =
        useState<MapLayerVisibility>(DEFAULT_MAP_LAYER_VISIBILITY);
    const layerVisibilityRef = useRef(layerVisibility);

    const bounds = useMemo(
        () => observedBounds(intel),
        [intel],
    );

    const links = useMemo(
        () => planetLinks(intel.planets),
        [intel.planets],
    );

    const shipPositions = useMemo(
        () => shipVisualPositions(intel, bounds),
        [bounds, intel],
    );

    const basesByPlanet = useMemo(
        () => starbaseByPlanetId(intel.starbases),
        [intel.starbases],
    );

    const linkedAccountId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;
    const orderDrafts = useMapOrderDrafts(intel, linkedAccountId);

    intelRef.current = intel;
    boundsRef.current = bounds;
    layerVisibilityRef.current = layerVisibility;

    useEffect(() => {
        const startPicking = (event: Event) => {
            const detail = (event as CustomEvent<{ shipId?: number }>).detail;
            if (typeof detail?.shipId !== "number") return;
            waypointPickShipIdRef.current = detail.shipId;
            setWaypointPickShipId(detail.shipId);
            if (appRef.current !== null) {
                appRef.current.canvas.style.cursor = "crosshair";
            }
        };

        const cancelPicking = (event: Event) => {
            const detail = (event as CustomEvent<{ shipId?: number }>).detail;
            if (
                typeof detail?.shipId === "number"
                && waypointPickShipIdRef.current !== detail.shipId
            ) return;
            const cancelledShipId = waypointPickShipIdRef.current;
            waypointPickShipIdRef.current = null;
            setWaypointPickShipId(null);
            if (appRef.current !== null) {
                appRef.current.canvas.style.cursor = "";
            }
            if (cancelledShipId !== null) {
                window.dispatchEvent(new CustomEvent("intel-waypoint-pick-cancelled", {
                    detail: { shipId: cancelledShipId },
                }));
            }
        };

        window.addEventListener("intel-waypoint-pick-start", startPicking);
        window.addEventListener("intel-waypoint-pick-cancel", cancelPicking);
        return () => {
            window.removeEventListener("intel-waypoint-pick-start", startPicking);
            window.removeEventListener("intel-waypoint-pick-cancel", cancelPicking);
        };
    }, []);

    useEffect(() => {
        let cancelled = false;
        const urls = Array.from(new Set(
            intel.ships
                .map((ship) => privateHullAssetUrl(ship.hull_id, ship.payload))
                .filter((value): value is string => value !== null),
        ));

        for (const url of urls) {
            if (
                loadedHullAssetUrlsRef.current.has(url) ||
                loadingHullAssetUrlsRef.current.has(url)
            ) {
                continue;
            }

            loadingHullAssetUrlsRef.current.add(url);
            void warmHullTexture(url)
                .then(() => {
                    if (cancelled) return;
                    loadedHullAssetUrlsRef.current.add(url);
                    setHullArtworkRevision((value) => value + 1);
                })
                .catch(() => {
                    // Keep the geometric marker. A later game/snapshot can retry.
                })
                .finally(() => {
                    loadingHullAssetUrlsRef.current.delete(url);
                });
        }

        return () => {
            cancelled = true;
        };
    }, [intel.game_id, intel.ships, intel.turn]);

    useEffect(() => {
        setSelectedCombatEvent(null);
        setSelectedHostEventKey(null);
    }, [intel.game_id, intel.turn]);

    useEffect(() => {
        let cancelled = false;

        async function loadTracks() {
            try {
                const response = await getHistoricalShipTracks(
                    intel.game_id,
                    linkedAccountId,
                    intel.turn,
                );
                if (!cancelled) {
                    setHistoricalTracks(response.tracks);
                }
            } catch {
                if (!cancelled) {
                    setHistoricalTracks([]);
                }
            }
        }

        void loadTracks();
        return () => {
            cancelled = true;
        };
    }, [intel.game_id, intel.turn, linkedAccountId]);

    useEffect(() => {
        let cancelled = false;

        async function loadHostEventMarkers() {
            try {
                const response = await getHostEvents(
                    intel.game_id,
                    linkedAccountId,
                    intel.turn,
                );
                if (!cancelled) {
                    setHostEvents(response.events);
                }
            } catch {
                if (!cancelled) {
                    setHostEvents([]);
                }
            }
        }

        void loadHostEventMarkers();
        return () => {
            cancelled = true;
        };
    }, [intel.game_id, intel.turn, linkedAccountId]);

    useEffect(() => {
        if (selectedCombatEvent === null) return;
        const selectedKey = combatEventKey(selectedCombatEvent);
        const stillPresent = historicalTracks.some((track) =>
            track.points.some(
                (point) =>
                    point.combat_event !== null &&
                    combatEventKey(point.combat_event) === selectedKey,
            ),
        );
        if (!stillPresent) setSelectedCombatEvent(null);
    }, [historicalTracks, selectedCombatEvent]);

    useEffect(() => {
        if (selectedHostEventKey === null) return;
        const stillPresent = hostEvents.some(
            (event) => hostEventKey(event) === selectedHostEventKey,
        );
        if (!stillPresent) setSelectedHostEventKey(null);
    }, [hostEvents, selectedHostEventKey]);

    useEffect(() => {
        const host = hostRef.current;
        if (host === null) return;

        let disposed = false;
        let resizeObserver: ResizeObserver | null = null;
        let detachInteractions: (() => void) | null = null;

        void (async () => {
            const nextApp = new Application();
            await nextApp.init({
                antialias: true,
                background: "#060a10",
                resizeTo: host,
                resolution: Math.min(window.devicePixelRatio || 1, 2),
                autoDensity: true,
                preference: "webgl",
            });

            if (disposed) {
                nextApp.destroy(true, true);
                return;
            }

            appRef.current = nextApp;
            host.replaceChildren(nextApp.canvas);
            nextApp.canvas.className = "intel-pixi-canvas";
            if (waypointPickShipIdRef.current !== null) {
                nextApp.canvas.style.cursor = "crosshair";
            }

            const world = new Container();
            worldRef.current = world;
            nextApp.stage.addChild(world);

            const hoverLayer = new Container();
            hoverLayer.visible = false;
            hoverLayer.eventMode = "none";
            const hoverBackground = new Graphics();
            const hoverText = new Text({
                text: "",
                style: {
                    fill: 0xe5eefb,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: 12,
                    lineHeight: 17,
                },
                resolution: 2,
            });
            hoverText.position.set(8, 6);
            hoverLayer.addChild(hoverBackground, hoverText);
            nextApp.stage.addChild(hoverLayer);
            hoverLayerRef.current = hoverLayer;
            hoverBackgroundRef.current = hoverBackground;
            hoverTextRef.current = hoverText;

            const fitView = () => {
                const currentBounds = boundsRef.current;
                const currentWorld = worldRef.current;
                const currentApp = appRef.current;
                if (
                    currentBounds === null ||
                    currentWorld === null ||
                    currentApp === null
                ) return;

                const viewportWidth = Math.max(currentApp.screen.width, 1);
                const viewportHeight = Math.max(currentApp.screen.height, 1);
                const worldWidth = Math.max(currentBounds.maxX - currentBounds.minX, 1);
                const worldHeight = Math.max(currentBounds.maxY - currentBounds.minY, 1);
                const horizontalScale = (viewportWidth - 70) / worldWidth;
                const verticalScale = (viewportHeight - 70) / worldHeight;
                const scale = Math.min(
                    Math.max(Math.min(horizontalScale, verticalScale), 0.08),
                    4,
                );
                const centerX = (currentBounds.minX + currentBounds.maxX) / 2;
                const factualCenterY = (
                    currentBounds.minY + currentBounds.maxY
                ) / 2;
                const centerY = renderY(factualCenterY, currentBounds);

                currentWorld.scale.set(scale);
                currentWorld.position.set(
                    viewportWidth / 2 - centerX * scale,
                    viewportHeight / 2 - centerY * scale,
                );
            };

            fitViewRef.current = fitView;
            lastFitGameIdRef.current = intelRef.current.game_id;
            fitView();

            const canvas = nextApp.canvas;
            let dragging = false;
            let pointerId: number | null = null;
            let lastX = 0;
            let lastY = 0;
            let pointerDownX = 0;
            let pointerDownY = 0;
            let pointerMoved = false;

            const screenPoint = (event: PointerEvent | WheelEvent) => {
                const rect = canvas.getBoundingClientRect();
                return {
                    x: (event.clientX - rect.left)
                        * (nextApp.screen.width / Math.max(rect.width, 1)),
                    y: (event.clientY - rect.top)
                        * (nextApp.screen.height / Math.max(rect.height, 1)),
                };
            };

            const hideHazardTooltip = () => {
                const layer = hoverLayerRef.current;
                if (layer !== null) layer.visible = false;
            };

            const updateHazardTooltip = (point: { x: number; y: number }) => {
                if (!layerVisibilityRef.current.entities) {
                    hideHazardTooltip();
                    return;
                }

                const currentWorld = worldRef.current;
                const currentIntel = intelRef.current;
                const layer = hoverLayerRef.current;
                const background = hoverBackgroundRef.current;
                const text = hoverTextRef.current;

                if (
                    currentWorld === null ||
                    layer === null || background === null || text === null
                ) return;

                const scale = Math.max(currentWorld.scale.x, 0.0001);
                const worldX = (point.x - currentWorld.position.x) / scale;
                const renderedY = (point.y - currentWorld.position.y) / scale;
                const factualY = -renderedY;
                const radiation = radiationAtPoint(currentIntel, worldX, factualY);
                const storm = ionStormAtPoint(currentIntel, worldX, factualY);
                const lines: string[] = [];

                if (radiation !== null) {
                    const clusterName = radiation.cluster.name
                        ?? `Star cluster #${radiation.cluster.feature_id}`;
                    if (radiation.insideCore) {
                        lines.push(`${clusterName}: CORE — ship destroyed`);
                    } else {
                        lines.push(`Radiation ${radiation.radiation} · ${clusterName}`);
                        lines.push(`Distance ${radiation.distance.toFixed(1)} ly from center`);
                    }
                }

                if (storm !== null) {
                    lines.push(`Ion ${Math.round(storm.localVoltage)} meV · Class ${storm.stormClass}`);
                    if (storm.randomTransportRisk) lines.push("Random long-range transport risk");
                }

                if (lines.length === 0) {
                    hideHazardTooltip();
                    return;
                }

                text.text = lines.join("\n");
                const width = text.width + 16;
                const height = text.height + 12;
                background
                    .clear()
                    .rect(0, 0, width, height)
                    .fill({ color: 0x0a111b, alpha: 0.94 })
                    .stroke({ color: 0x3b506b, width: 1, alpha: 0.9 });

                layer.position.set(
                    Math.min(point.x + 14, Math.max(nextApp.screen.width - width - 6, 6)),
                    Math.min(point.y + 14, Math.max(nextApp.screen.height - height - 6, 6)),
                );
                layer.visible = true;
            };

            const handlePointerDown = (event: PointerEvent) => {
                if (event.button !== 0) return;
                const point = screenPoint(event);
                dragging = true;
                pointerId = event.pointerId;
                lastX = point.x;
                lastY = point.y;
                pointerDownX = point.x;
                pointerDownY = point.y;
                pointerMoved = false;
                hideHazardTooltip();
                canvas.setPointerCapture(event.pointerId);
                canvas.classList.add("is-dragging");
            };

            const handlePointerMove = (event: PointerEvent) => {
                const point = screenPoint(event);
                const currentWorld = worldRef.current;
                if (dragging && pointerId === event.pointerId && currentWorld !== null) {
                    if (
                        Math.hypot(
                            point.x - pointerDownX,
                            point.y - pointerDownY,
                        ) > 4
                    ) {
                        pointerMoved = true;
                    }
                    currentWorld.position.x += point.x - lastX;
                    currentWorld.position.y += point.y - lastY;
                    lastX = point.x;
                    lastY = point.y;
                    hideHazardTooltip();
                    return;
                }
                if (!dragging) updateHazardTooltip(point);
            };

            const stopDragging = (event: PointerEvent) => {
                if (pointerId !== event.pointerId) return;
                const point = screenPoint(event);
                dragging = false;
                pointerId = null;
                canvas.classList.remove("is-dragging");
                if (canvas.hasPointerCapture(event.pointerId)) {
                    canvas.releasePointerCapture(event.pointerId);
                }

                const pickingShipId = waypointPickShipIdRef.current;
                const currentWorld = worldRef.current;
                if (
                    pickingShipId !== null
                    && !pointerMoved
                    && currentWorld !== null
                ) {
                    const scale = Math.max(currentWorld.scale.x, 0.0001);
                    const worldX = (point.x - currentWorld.position.x) / scale;
                    const renderedY = (point.y - currentWorld.position.y) / scale;
                    const factualY = -renderedY;
                    waypointPickShipIdRef.current = null;
                    setWaypointPickShipId(null);
                    canvas.style.cursor = "";
                    hideHazardTooltip();
                    window.dispatchEvent(new CustomEvent("intel-waypoint-picked", {
                        detail: {
                            shipId: pickingShipId,
                            x: Math.round(worldX),
                            y: Math.round(factualY),
                        },
                    }));
                    return;
                }

                updateHazardTooltip(point);
            };

            const handleWheel = (event: WheelEvent) => {
                event.preventDefault();
                hideHazardTooltip();
                const currentWorld = worldRef.current;
                if (currentWorld === null) return;

                const point = screenPoint(event);
                const oldScale = currentWorld.scale.x;
                const factor = event.deltaY < 0 ? 1.12 : 0.89;
                const nextScale = Math.min(Math.max(oldScale * factor, 0.05), 10);
                const worldX = (point.x - currentWorld.position.x) / oldScale;
                const worldY = (point.y - currentWorld.position.y) / oldScale;
                currentWorld.scale.set(nextScale);
                currentWorld.position.set(
                    point.x - worldX * nextScale,
                    point.y - worldY * nextScale,
                );
            };

            canvas.addEventListener("pointerdown", handlePointerDown);
            canvas.addEventListener("pointermove", handlePointerMove);
            canvas.addEventListener("pointerup", stopDragging);
            canvas.addEventListener("pointercancel", stopDragging);
            canvas.addEventListener("pointerleave", hideHazardTooltip);
            canvas.addEventListener("wheel", handleWheel, { passive: false });

            detachInteractions = () => {
                canvas.removeEventListener("pointerdown", handlePointerDown);
                canvas.removeEventListener("pointermove", handlePointerMove);
                canvas.removeEventListener("pointerup", stopDragging);
                canvas.removeEventListener("pointercancel", stopDragging);
                canvas.removeEventListener("pointerleave", hideHazardTooltip);
                canvas.removeEventListener("wheel", handleWheel);
            };

            resizeObserver = new ResizeObserver(() => {
                window.requestAnimationFrame(() => {
                    if (!disposed) nextApp.resize();
                });
            });
            resizeObserver.observe(host);
            setAppReadyRevision((value) => value + 1);
        })();

        return () => {
            disposed = true;
            fitViewRef.current = null;
            resizeObserver?.disconnect();
            detachInteractions?.();
            hoverLayerRef.current = null;
            hoverBackgroundRef.current = null;
            hoverTextRef.current = null;
            worldRef.current = null;

            const currentApp = appRef.current;
            appRef.current = null;
            if (currentApp !== null) currentApp.destroy(true, true);
        };
    }, [fitViewRef]);

    useEffect(() => {
        const world = worldRef.current;
        if (world === null) return;

        const oldChildren = world.removeChildren();
        for (const child of oldChildren) child.destroy();

        const selectMapEntity = (entity: SelectedEntity) => {
            if (waypointPickShipIdRef.current !== null) return;
            onSelect(entity);
        };

        if (layerVisibility.minefields) {
            drawMinefields({
                world,
                intel,
                bounds,
                selected,
                onSelect: selectMapEntity,
            });
        }

        if (layerVisibility.historicalTracks) {
            drawHistoricalShipTracks({
                world,
                tracks: historicalTracks,
                bounds,
                selected,
                mode: trackMode,
                throughTurn: intel.turn,
                lookbackTurns: trackLookbackTurns,
                fadePerTurn: trackFadePercent / 100,
            });
        }

        if (layerVisibility.entities) {
            drawMapScene({
                world,
                intel,
                bounds,
                links,
                shipPositions,
                basesByPlanet,
                labelMode,
                selected,
                onSelect: selectMapEntity,
                loadedHullAssetUrls: loadedHullAssetUrlsRef.current,
            });
        }

        if (layerVisibility.movementPredictions) {
            drawOrderVectors({
                world,
                intel,
                bounds,
                selected,
                drafts: orderDrafts,
            });
        }

        if (layerVisibility.combatEvents) {
            drawCurrentCombatContacts({
                world,
                tracks: historicalTracks,
                bounds,
                throughTurn: intel.turn,
                visibleShipIds: new Set(
                    shipPositions.map((position) => position.ship.ship_id),
                ),
                selectedEventKey: selectedCombatEvent === null
                    ? null
                    : combatEventKey(selectedCombatEvent),
                onSelectEvent: (event) => {
                    if (waypointPickShipIdRef.current === null) {
                        setSelectedCombatEvent(event);
                    }
                },
            });
        } else {
            clearCurrentCombatContacts(intel.turn);
        }

        if (layerVisibility.hostEvents) {
            drawHostEvents({
                world,
                events: hostEvents,
                bounds,
                selectedKey: selectedHostEventKey,
                onSelect: (event) => {
                    if (waypointPickShipIdRef.current !== null) return;
                    const key = hostEventKey(event);
                    setSelectedHostEventKey(key);
                    window.dispatchEvent(new CustomEvent("dashboard-host-event-select", {
                        detail: { key },
                    }));
                },
            });
        }

        if (hoverLayerRef.current !== null) hoverLayerRef.current.visible = false;

        if (lastFitGameIdRef.current !== intel.game_id) {
            lastFitGameIdRef.current = intel.game_id;
            window.requestAnimationFrame(() => fitViewRef.current?.());
        }
    }, [
        appReadyRevision,
        basesByPlanet,
        bounds,
        fitViewRef,
        historicalTracks,
        hostEvents,
        hullArtworkRevision,
        intel,
        labelMode,
        layerVisibility,
        links,
        onSelect,
        orderDrafts,
        selected,
        selectedCombatEvent,
        selectedHostEventKey,
        shipPositions,
        trackFadePercent,
        trackLookbackTurns,
        trackMode,
    ]);

    const combatHasDerivedSequence = selectedCombatEvent?.sides.some(
        (side) =>
            side.object_kind === "ship" &&
            side.sequence_status !== null &&
            side.sequence_status !== "unknown",
    ) ?? false;

    const focusCombatEvent = (event: CombatEventSummary) => {
        const app = appRef.current;
        const world = worldRef.current;
        const currentBounds = boundsRef.current;
        if (
            app === null ||
            world === null ||
            currentBounds === null ||
            event.x === null ||
            event.y === null
        ) {
            return;
        }

        const scale = Math.max(world.scale.x, 0.0001);
        const targetY = renderY(event.y, currentBounds);
        world.position.set(
            app.screen.width / 2 - event.x * scale,
            app.screen.height / 2 - targetY * scale,
        );
    };

    return (
        <>
            <div className="intel-map-canvas-host" ref={hostRef} />

            {waypointPickShipId !== null && (
                <div
                    style={{
                        position: "absolute",
                        zIndex: 6,
                        left: "50%",
                        top: 12,
                        transform: "translateX(-50%)",
                        padding: "7px 11px",
                        border: "1px solid rgba(98, 184, 255, 0.65)",
                        borderRadius: 7,
                        background: "rgba(8, 17, 28, 0.94)",
                        color: "#a9dbff",
                        fontSize: 12,
                        fontWeight: 700,
                        pointerEvents: "none",
                    }}
                >
                    Pick waypoint for ship #{waypointPickShipId} · click map
                </div>
            )}

            <MapLayerControls
                onChange={setLayerVisibility}
                visibility={layerVisibility}
            />

            {layerVisibility.historicalTracks && (
                <TrackControls
                    fadePercent={trackFadePercent}
                    lookbackTurns={trackLookbackTurns}
                    mode={trackMode}
                    onFadeChange={setTrackFadePercent}
                    onLookbackChange={setTrackLookbackTurns}
                    onModeChange={setTrackMode}
                />
            )}

            <CombatEventPanel
                gameId={intel.game_id}
                linkedAccountId={linkedAccountId}
                onFocus={focusCombatEvent}
                turn={intel.turn}
            />

            {layerVisibility.combatEvents && selectedCombatEvent !== null && (
                <div
                    style={{
                        position: "absolute",
                        zIndex: 5,
                        right: 12,
                        bottom: 12,
                        width: "min(370px, calc(100% - 24px))",
                        padding: "12px 13px",
                        border: "1px solid rgba(255, 204, 115, 0.55)",
                        borderRadius: 9,
                        background: "rgba(8, 13, 21, 0.96)",
                        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.38)",
                        backdropFilter: "blur(6px)",
                    }}
                >
                    <div
                        style={{
                            display: "flex",
                            alignItems: "flex-start",
                            justifyContent: "space-between",
                            gap: 12,
                        }}
                    >
                        <div>
                            <div className="eyebrow">Combat event</div>
                            <strong>
                                VCR #{selectedCombatEvent.vcr_id} · T{selectedCombatEvent.turn}
                            </strong>
                            <div style={{ color: "#91a9c8", marginTop: 3, fontSize: 12 }}>
                                {combatEventKind(selectedCombatEvent)}
                                {selectedCombatEvent.sequence_count > 1
                                    ? ` · ${selectedCombatEvent.sequence_index}/${selectedCombatEvent.sequence_count} at this position`
                                    : ""}
                                {selectedCombatEvent.x !== null && selectedCombatEvent.y !== null
                                    ? ` · ${selectedCombatEvent.x}, ${selectedCombatEvent.y}`
                                    : ""}
                            </div>
                        </div>
                        <button
                            className="secondary-button"
                            onClick={() => setSelectedCombatEvent(null)}
                            style={{ padding: "4px 8px" }}
                            type="button"
                        >
                            Close
                        </button>
                    </div>

                    <div
                        style={{
                            display: "grid",
                            gap: 8,
                            marginTop: 11,
                        }}
                    >
                        {selectedCombatEvent.sides.map((side) => (
                            <div
                                key={side.side}
                                style={{
                                    padding: "8px 9px",
                                    border: "1px solid #26374d",
                                    borderRadius: 6,
                                    background: "#0b1420",
                                }}
                            >
                                <strong>{combatSideName(side)}</strong>
                                <div style={{ color: "#8ba1bd", marginTop: 3, fontSize: 12 }}>
                                    {side.object_kind === "ship"
                                        ? `Ship ${side.object_id === null ? "?" : `#${side.object_id}`}`
                                        : `Planet ${side.object_id === null ? "?" : `#${side.object_id}`}`}
                                    {side.hull_id !== null ? ` · hull #${side.hull_id}` : ""}
                                    {side.owner_id !== null ? ` · VCR owner slot ${side.owner_id}` : ""}
                                </div>
                                {side.object_kind === "ship" && (
                                    <div style={{ marginTop: 4, fontSize: 12 }}>
                                        {side.post_host_confirmed ? (
                                            <span style={{ color: "#82e6b1" }}>
                                                Survived host · directly observed afterwards
                                            </span>
                                        ) : (
                                            <span style={{ color: side.combat_outcome === "defeated" ? "#ff8b99" : "#e8c778" }}>
                                                {combatOutcomeLabel(side.combat_outcome)}
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    {combatHasDerivedSequence && (
                        <div
                            style={{
                                marginTop: 9,
                                paddingTop: 8,
                                borderTop: "1px solid #28384c",
                                color: "#8da3be",
                                fontSize: 11,
                            }}
                        >
                            Combat sequence status is derived only from stored factual VCR order at the same position.
                        </div>
                    )}
                </div>
            )}
        </>
    );
}
