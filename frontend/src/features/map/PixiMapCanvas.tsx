import {
    type MutableRefObject,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import { Application, Container, Graphics, Text } from "pixi.js";
import { getHistoricalShipTracks } from "../../api/history";
import type { HistoricalShipTrack } from "../../types/history";
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
import { drawMapScene } from "./mapScene";
import { drawHistoricalShipTracks } from "./historicalTrackScene";
import { drawMinefields } from "./minefieldScene";


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
    const [appReadyRevision, setAppReadyRevision] = useState(0);
    const [historicalTracks, setHistoricalTracks] =
        useState<HistoricalShipTrack[]>([]);

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

    intelRef.current = intel;
    boundsRef.current = bounds;

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
                hideHazardTooltip();
                canvas.setPointerCapture(event.pointerId);
                canvas.classList.add("is-dragging");
            };

            const handlePointerMove = (event: PointerEvent) => {
                const point = screenPoint(event);
                const currentWorld = worldRef.current;
                if (dragging && pointerId === event.pointerId && currentWorld !== null) {
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
                dragging = false;
                pointerId = null;
                canvas.classList.remove("is-dragging");
                if (canvas.hasPointerCapture(event.pointerId)) {
                    canvas.releasePointerCapture(event.pointerId);
                }
                updateHazardTooltip(screenPoint(event));
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

        drawMinefields({
            world,
            intel,
            bounds,
            selected,
            onSelect,
        });

        drawHistoricalShipTracks({
            world,
            tracks: historicalTracks,
            bounds,
            selected,
            mode: "all",
        });

        drawMapScene({
            world,
            intel,
            bounds,
            links,
            shipPositions,
            basesByPlanet,
            labelMode,
            selected,
            onSelect,
        });

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
        intel,
        labelMode,
        links,
        onSelect,
        selected,
        shipPositions,
    ]);

    return <div className="intel-map-canvas-host" ref={hostRef} />;
}
