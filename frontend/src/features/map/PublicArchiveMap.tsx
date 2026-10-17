import { useEffect, useMemo, useRef, useState } from "react";
import { Application, Container } from "pixi.js";
import type { PublicArchiveTurn } from "../../types/publicArchive";
import { drawMapScene } from "./mapScene";
import {
    observedBounds,
    planetLinks,
    renderY,
    shipVisualPositions,
    starbaseByPlanetId,
    type SelectedEntity,
} from "./mapModel";
import { planetFacts } from "./observationView";
import "./map.css";

/** The existing Pixi factual map renderer, without private observer hooks,
 * historical private requests, order drafts, or linked account impersonation.
 */
export function PublicArchiveMap({ archive }: { archive: PublicArchiveTurn }) {
    const hostRef = useRef<HTMLDivElement>(null);
    const appRef = useRef<Application | null>(null);
    const worldRef = useRef<Container | null>(null);
    const fitRevisionRef = useRef<string | null>(null);
    const [ready, setReady] = useState(false);
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const bounds = useMemo(() => observedBounds(archive), [archive]);
    const links = useMemo(() => planetLinks(archive.planets), [archive.planets]);
    const ships = useMemo(() => shipVisualPositions(archive, bounds), [archive, bounds]);
    const bases = useMemo(() => starbaseByPlanetId(archive.starbases), [archive.starbases]);

    useEffect(() => {
        const host = hostRef.current;
        if (host === null) return;
        const app = new Application();
        let disposed = false;
        let initialized = false;
        let cleanup: (() => void) | null = null;
        void (async () => {
            await app.init({
                background: "#080f1b",
                antialias: true,
                resizeTo: host,
            });
            initialized = true;
            if (disposed) {
                app.destroy(true, true);
                return;
            }
            host.appendChild(app.canvas);
            appRef.current = app;
            const world = new Container();
            worldRef.current = world;
            app.stage.addChild(world);
            let dragging = false;
            let previousX = 0;
            let previousY = 0;
            const down = (e: PointerEvent) => {
                if (e.button !== 0) return;
                dragging = true;
                previousX = e.clientX;
                previousY = e.clientY;
                app.canvas.setPointerCapture(e.pointerId);
            };
            const move = (e: PointerEvent) => {
                if (!dragging) return;
                const rect = app.canvas.getBoundingClientRect();
                const sx = app.screen.width / Math.max(rect.width, 1);
                const sy = app.screen.height / Math.max(rect.height, 1);
                world.position.x += (e.clientX - previousX) * sx;
                world.position.y += (e.clientY - previousY) * sy;
                previousX = e.clientX;
                previousY = e.clientY;
            };
            const up = (e: PointerEvent) => {
                dragging = false;
                if (app.canvas.hasPointerCapture(e.pointerId)) {
                    app.canvas.releasePointerCapture(e.pointerId);
                }
            };
            const wheel = (e: WheelEvent) => {
                e.preventDefault();
                const rect = app.canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) * (app.screen.width / Math.max(rect.width, 1));
                const y = (e.clientY - rect.top) * (app.screen.height / Math.max(rect.height, 1));
                const old = world.scale.x;
                const next = Math.min(10, Math.max(.05, old * (e.deltaY < 0 ? 1.12 : .89)));
                world.scale.set(next);
                world.position.set(
                    x - (x - world.position.x) * next / old,
                    y - (y - world.position.y) * next / old,
                );
            };
            app.canvas.addEventListener("pointerdown", down);
            app.canvas.addEventListener("pointermove", move);
            app.canvas.addEventListener("pointerup", up);
            app.canvas.addEventListener("pointercancel", up);
            app.canvas.addEventListener("wheel", wheel, { passive: false });
            cleanup = () => {
                app.canvas.removeEventListener("pointerdown", down);
                app.canvas.removeEventListener("pointermove", move);
                app.canvas.removeEventListener("pointerup", up);
                app.canvas.removeEventListener("pointercancel", up);
                app.canvas.removeEventListener("wheel", wheel);
            };
            setReady(true);
        })();
        return () => {
            disposed = true;
            cleanup?.();
            appRef.current = null;
            worldRef.current = null;
            if (initialized && !disposed) app.destroy(true, true);
        };
    }, []);

    useEffect(() => {
        const world = worldRef.current;
        const app = appRef.current;
        if (!ready || world === null || app === null) return;
        const old = world.removeChildren();
        for (const child of old) child.destroy();
        drawMapScene({
            world,
            intel: archive,
            bounds,
            links,
            shipPositions: ships,
            basesByPlanet: bases,
            labelMode: "name",
            selected,
            onSelect: setSelected,
            loadedHullAssetUrls: new Set<string>(),
        });
        const revision = `${archive.game_id}:${archive.player_slot_id}:${archive.turn}`;
        if (fitRevisionRef.current === revision) return;
        fitRevisionRef.current = revision;
        const width = Math.max(bounds.maxX - bounds.minX, 1);
        const height = Math.max(bounds.maxY - bounds.minY, 1);
        const scale = Math.max(.05, Math.min(
            (app.screen.width - 70) / width,
            (app.screen.height - 70) / height,
            4,
        ));
        world.scale.set(scale);
        world.position.set(
            app.screen.width / 2 - ((bounds.minX + bounds.maxX) / 2) * scale,
            app.screen.height / 2 - renderY((bounds.minY + bounds.maxY) / 2, bounds) * scale,
        );
    }, [ready, archive, bounds, links, ships, bases, selected]);

    useEffect(() => setSelected(null), [archive.game_id, archive.turn, archive.player_slot_id]);

    const details = selected === null ? null : selected.kind === "planet"
        ? planetFacts(selected.value)
        : selected.value.payload;
    return (
        <section className="panel intel-map-panel">
            <div className="panel-header intel-map-header">
                <div>
                    <div className="eyebrow">Finished public archive · read-only</div>
                    <h2>Starmap · T{archive.turn}</h2>
                    <p>Historical perspective: slot #{archive.player_slot_id}. Only entities revealed in this RST are factual.</p>
                </div>
            </div>
            <div className="intel-map-workspace" style={{ minHeight: 520 }}>
                <div className="intel-map-canvas-host" ref={hostRef} style={{ height: 520, minHeight: 520 }} />
            </div>
            {selected !== null && (
                <div style={{ margin: "12px 22px 22px" }}>
                    <strong>{selected.kind} · {"name" in selected.value ? selected.value.name ?? "Unnamed" : "Selected"}</strong>
                    <pre style={{ overflowX: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(details, null, 2)}</pre>
                </div>
            )}
        </section>
    );
}
