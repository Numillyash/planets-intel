import { type MutableRefObject, useEffect, useMemo, useRef } from "react";
import { Application, Container, Graphics, Text } from "pixi.js";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    observedBounds,
    planetLinks,
    shipVisualPositions,
    starbaseByPlanetId,
    type PlanetLabelMode,
    type SelectedEntity,
} from "./mapModel";
import {
    ionStormAtPoint,
    radiationAtPoint,
} from "./navigationAnalysis";
import { drawMapScene } from "./mapScene";


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

    useEffect(() => {
        const host = hostRef.current;

        if (host === null) {
            return;
        }

        let disposed = false;
        let app: Application | null = null;
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

            app = nextApp;
            host.replaceChildren(nextApp.canvas);
            nextApp.canvas.className = "intel-pixi-canvas";

            const world = new Container();
            nextApp.stage.addChild(world);

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

            const fitView = () => {
                const viewportWidth = Math.max(nextApp.screen.width, 1);
                const viewportHeight = Math.max(nextApp.screen.height, 1);
                const worldWidth = Math.max(bounds.maxX - bounds.minX, 1);
                const worldHeight = Math.max(bounds.maxY - bounds.minY, 1);
                const horizontalScale = (viewportWidth - 70) / worldWidth;
                const verticalScale = (viewportHeight - 70) / worldHeight;
                const scale = Math.min(
                    Math.max(Math.min(horizontalScale, verticalScale), 0.08),
                    4,
                );
                const centerX = (bounds.minX + bounds.maxX) / 2;
                const centerY = (bounds.minY + bounds.maxY) / 2;

                world.scale.set(scale);
                world.position.set(
                    viewportWidth / 2 - centerX * scale,
                    viewportHeight / 2 - centerY * scale,
                );
            };

            fitViewRef.current = fitView;
            fitView();

            const canvas = nextApp.canvas;
            let dragging = false;
            let pointerId: number | null = null;
            let lastX = 0;
            let lastY = 0;

            const screenPoint = (event: PointerEvent | WheelEvent) => {
                const rect = canvas.getBoundingClientRect();
                return {
                    x:
                        (event.clientX - rect.left)
                        * (nextApp.screen.width / Math.max(rect.width, 1)),
                    y:
                        (event.clientY - rect.top)
                        * (nextApp.screen.height / Math.max(rect.height, 1)),
                };
            };

            const hideHazardTooltip = () => {
                hoverLayer.visible = false;
            };

            const updateHazardTooltip = (point: { x: number; y: number }) => {
                const scale = Math.max(world.scale.x, 0.0001);
                const worldX = (point.x - world.position.x) / scale;
                const renderedY = (point.y - world.position.y) / scale;
                const factualY = bounds.minY + bounds.maxY - renderedY;
                const radiation = radiationAtPoint(intel, worldX, factualY);
                const storm = ionStormAtPoint(intel, worldX, factualY);
                const lines: string[] = [];

                if (radiation !== null) {
                    const clusterName = radiation.cluster.name
                        ?? `Star cluster #${radiation.cluster.feature_id}`;
                    if (radiation.insideCore) {
                        lines.push(`${clusterName}: CORE — ship destroyed`);
                    } else {
                        lines.push(
                            `Radiation ${radiation.radiation} · ${clusterName}`,
                        );
                        lines.push(
                            `Distance ${radiation.distance.toFixed(1)} ly from center`,
                        );
                    }
                }

                if (storm !== null) {
                    lines.push(
                        `Ion ${Math.round(storm.localVoltage)} meV · Class ${storm.stormClass}`,
                    );
                    if (storm.randomTransportRisk) {
                        lines.push("Random long-range transport risk");
                    }
                }

                if (lines.length === 0) {
                    hideHazardTooltip();
                    return;
                }

                hoverText.text = lines.join("\n");
                const width = hoverText.width + 16;
                const height = hoverText.height + 12;
                hoverBackground
                    .clear()
                    .rect(0, 0, width, height)
                    .fill({ color: 0x0a111b, alpha: 0.94 })
                    .stroke({ color: 0x3b506b, width: 1, alpha: 0.9 });

                hoverLayer.position.set(
                    Math.min(point.x + 14, Math.max(nextApp.screen.width - width - 6, 6)),
                    Math.min(point.y + 14, Math.max(nextApp.screen.height - height - 6, 6)),
                );
                hoverLayer.visible = true;
            };

            const handlePointerDown = (event: PointerEvent) => {
                if (event.button !== 0) {
                    return;
                }

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

                if (dragging && pointerId === event.pointerId) {
                    world.position.x += point.x - lastX;
                    world.position.y += point.y - lastY;
                    lastX = point.x;
                    lastY = point.y;
                    hideHazardTooltip();
                    return;
                }

                if (!dragging) {
                    updateHazardTooltip(point);
                }
            };

            const stopDragging = (event: PointerEvent) => {
                if (pointerId !== event.pointerId) {
                    return;
                }

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

                const point = screenPoint(event);
                const oldScale = world.scale.x;
                const factor = event.deltaY < 0 ? 1.12 : 0.89;
                const nextScale = Math.min(
                    Math.max(oldScale * factor, 0.05),
                    10,
                );

                const worldX = (point.x - world.position.x) / oldScale;
                const worldY = (point.y - world.position.y) / oldScale;

                world.scale.set(nextScale);
                world.position.set(
                    point.x - worldX * nextScale,
                    point.y - worldY * nextScale,
                );
            };

            canvas.addEventListener("pointerdown", handlePointerDown);
            canvas.addEventListener("pointermove", handlePointerMove);
            canvas.addEventListener("pointerup", stopDragging);
            canvas.addEventListener("pointercancel", stopDragging);
            canvas.addEventListener("pointerleave", hideHazardTooltip);
            canvas.addEventListener("wheel", handleWheel, {
                passive: false,
            });

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
                    if (!disposed) {
                        nextApp.resize();
                    }
                });
            });
            resizeObserver.observe(host);
        })();

        return () => {
            disposed = true;
            fitViewRef.current = null;
            resizeObserver?.disconnect();
            detachInteractions?.();

            if (app !== null) {
                app.destroy(true, true);
            }
        };
    }, [
        basesByPlanet,
        bounds,
        fitViewRef,
        intel,
        labelMode,
        links,
        onSelect,
        selected,
        shipPositions,
    ]);

    return <div className="intel-map-canvas-host" ref={hostRef} />;
}
