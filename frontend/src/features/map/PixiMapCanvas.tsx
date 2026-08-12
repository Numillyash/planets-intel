import { type MutableRefObject, useEffect, useMemo, useRef } from "react";
import { Application, Container } from "pixi.js";
import type { LatestPrivateIntelResponse } from "../../types/api";
import {
    observedBounds,
    planetLinks,
    shipVisualPositions,
    starbaseByPlanetId,
    type PlanetLabelMode,
    type SelectedEntity,
} from "./mapModel";
import { drawMapScene } from "./mapScene";

export function PixiMapCanvas({
    intel,
    labelMode,
    onSelect,
    fitViewRef,
}: {
    intel: LatestPrivateIntelResponse;
    labelMode: PlanetLabelMode;
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
                onSelect,
            });

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

            const handlePointerDown = (event: PointerEvent) => {
                if (event.button !== 0) {
                    return;
                }

                const point = screenPoint(event);
                dragging = true;
                pointerId = event.pointerId;
                lastX = point.x;
                lastY = point.y;
                canvas.setPointerCapture(event.pointerId);
                canvas.classList.add("is-dragging");
            };

            const handlePointerMove = (event: PointerEvent) => {
                if (!dragging || pointerId !== event.pointerId) {
                    return;
                }

                const point = screenPoint(event);
                world.position.x += point.x - lastX;
                world.position.y += point.y - lastY;
                lastX = point.x;
                lastY = point.y;
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
            };

            const handleWheel = (event: WheelEvent) => {
                event.preventDefault();

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
            canvas.addEventListener("wheel", handleWheel, {
                passive: false,
            });

            detachInteractions = () => {
                canvas.removeEventListener("pointerdown", handlePointerDown);
                canvas.removeEventListener("pointermove", handlePointerMove);
                canvas.removeEventListener("pointerup", stopDragging);
                canvas.removeEventListener("pointercancel", stopDragging);
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
        shipPositions,
    ]);

    return <div className="intel-map-canvas-host" ref={hostRef} />;
}


