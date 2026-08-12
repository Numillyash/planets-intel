import {
    type MutableRefObject,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import {
    Application,
    Container,
    Graphics,
    Text,
} from "pixi.js";

import type {
    LatestPrivateIntelResponse,
    PlanetObservationResponse,
    PlayerInfo,
    ShipObservationResponse,
    StarbaseObservationResponse,
} from "../../types/api";
import {
    PLANET_LINK_RANGE,
    SHIP_ROLE_LABEL,
    observedBounds,
    planetLabel,
    planetLinks,
    renderY,
    shipRole,
    type PlanetLabelMode,
    type ShipRole,
} from "./mapModel";
import "./map.css";


type SelectedEntity =
    | {
        kind: "planet";
        value: PlanetObservationResponse;
    }
    | {
        kind: "ship";
        value: ShipObservationResponse;
    }
    | {
        kind: "starbase";
        value: StarbaseObservationResponse;
    };


interface PrivateIntelMapProps {
    intel: LatestPrivateIntelResponse | null;
    loading: boolean;
    error: string | null;
    observerName: string;
    players: PlayerInfo[];
}


const OWNER_COLORS = [
    0x60a5fa,
    0xf87171,
    0x4ade80,
    0xfbbf24,
    0xc084fc,
    0x22d3ee,
    0xfb7185,
    0xa3e635,
    0xf97316,
    0x818cf8,
    0x2dd4bf,
];


function ownerColor(ownerId: number | null): number {
    if (ownerId === null || ownerId <= 0) {
        return 0x7b8798;
    }

    return OWNER_COLORS[(ownerId - 1) % OWNER_COLORS.length];
}


function playerName(
    ownerId: number | null,
    players: PlayerInfo[],
): string {
    if (ownerId === null || ownerId <= 0) {
        return "Unknown / unowned";
    }

    const player = players.find(
        (item) => item.slot_id === ownerId,
    );

    return player
        ? `${player.username} (slot ${ownerId})`
        : `Slot ${ownerId}`;
}


function formatObservedAt(value: string): string {
    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleString();
}


function shipMarker(role: ShipRole, color: number): Graphics {
    const marker = new Graphics();

    if (role === "freighter") {
        marker.rect(-7, -7, 14, 14);
    } else if (role === "carrier") {
        marker.poly([
            0, -9,
            8, -4,
            8, 4,
            0, 9,
            -8, 4,
            -8, -4,
        ]);
    } else if (role === "torpedo") {
        marker.poly([
            0, -9,
            8, 8,
            -8, 8,
        ]);
    } else {
        marker.poly([
            0, -9,
            8, 0,
            0, 9,
            -8, 0,
        ]);
    }

    marker
        .fill({ color, alpha: 0.95 })
        .stroke({
            color: 0xffffff,
            width: 1,
            alpha: 0.72,
        });

    return marker;
}


function EntityDetails({
    selected,
    players,
}: {
    selected: SelectedEntity | null;
    players: PlayerInfo[];
}) {
    if (selected === null) {
        return (
            <div className="intel-map-empty-selection">
                <strong>Select an entity</strong>
                <p>
                    Click a planet, ship, or starbase marker to inspect the
                    factual observation stored for this observer.
                </p>
            </div>
        );
    }

    if (selected.kind === "planet") {
        const planet = selected.value;
        return (
            <div className="intel-entity-details">
                <span className="intel-entity-kind">Planet</span>
                <h3>{planet.name ?? `Planet ${planet.planet_id}`}</h3>
                <dl>
                    <div><dt>ID</dt><dd>{planet.planet_id}</dd></div>
                    <div><dt>Owner</dt><dd>{playerName(planet.owner_id, players)}</dd></div>
                    <div><dt>Info turn</dt><dd>{planet.info_turn ?? "—"}</dd></div>
                    <div><dt>X</dt><dd>{planet.x ?? "—"}</dd></div>
                    <div><dt>Y</dt><dd>{planet.y ?? "—"}</dd></div>
                </dl>
            </div>
        );
    }

    if (selected.kind === "ship") {
        const ship = selected.value;
        const role = shipRole(ship);
        return (
            <div className="intel-entity-details">
                <span className="intel-entity-kind">Ship</span>
                <h3>{ship.name ?? `Ship ${ship.ship_id}`}</h3>
                <dl>
                    <div><dt>ID</dt><dd>{ship.ship_id}</dd></div>
                    <div><dt>Role</dt><dd>{SHIP_ROLE_LABEL[role]}</dd></div>
                    <div><dt>Owner</dt><dd>{playerName(ship.owner_id, players)}</dd></div>
                    <div><dt>Hull ID</dt><dd>{ship.hull_id ?? "—"}</dd></div>
                    <div><dt>Warp</dt><dd>{ship.warp ?? "—"}</dd></div>
                    <div><dt>Info turn</dt><dd>{ship.info_turn ?? "—"}</dd></div>
                    <div><dt>X</dt><dd>{ship.x ?? "—"}</dd></div>
                    <div><dt>Y</dt><dd>{ship.y ?? "—"}</dd></div>
                </dl>
            </div>
        );
    }

    const starbase = selected.value;
    return (
        <div className="intel-entity-details">
            <span className="intel-entity-kind">Starbase</span>
            <h3>Starbase {starbase.starbase_id}</h3>
            <dl>
                <div><dt>ID</dt><dd>{starbase.starbase_id}</dd></div>
                <div><dt>Planet ID</dt><dd>{starbase.planet_id ?? "—"}</dd></div>
                <div><dt>Race ID</dt><dd>{starbase.race_id ?? "—"}</dd></div>
                <div><dt>Info turn</dt><dd>{starbase.info_turn ?? "—"}</dd></div>
            </dl>
        </div>
    );
}


function PixiMapCanvas({
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

            const linkLayer = new Graphics();
            for (const link of links) {
                if (
                    link.from.x === null || link.from.y === null ||
                    link.to.x === null || link.to.y === null
                ) {
                    continue;
                }

                linkLayer
                    .moveTo(
                        link.from.x,
                        renderY(link.from.y, bounds),
                    )
                    .lineTo(
                        link.to.x,
                        renderY(link.to.y, bounds),
                    );
            }
            linkLayer.stroke({
                color: 0x34465e,
                width: 1,
                alpha: 0.46,
            });
            world.addChild(linkLayer);

            const planetById = new Map(
                intel.planets.map((planet) => [planet.planet_id, planet]),
            );

            for (const planet of intel.planets) {
                if (planet.x === null || planet.y === null) {
                    continue;
                }

                const y = renderY(planet.y, bounds);
                const marker = new Graphics()
                    .circle(0, 0, 7)
                    .fill(ownerColor(planet.owner_id))
                    .stroke({
                        color: 0xf4f7fb,
                        width: 1.2,
                        alpha: 0.55,
                    });

                marker.position.set(planet.x, y);
                marker.eventMode = "static";
                marker.cursor = "pointer";
                marker.on("pointertap", (event) => {
                    event.stopPropagation();
                    onSelect({
                        kind: "planet",
                        value: planet,
                    });
                });
                world.addChild(marker);

                const labelText = planetLabel(planet, labelMode);
                if (labelText !== null) {
                    const label = new Text({
                        text: labelText,
                        style: {
                            fill: 0xb9c6d8,
                            fontFamily: "Inter, Arial, sans-serif",
                            fontSize: 11,
                            stroke: {
                                color: 0x060a10,
                                width: 3,
                            },
                        },
                        resolution: 2,
                    });
                    label.position.set(
                        planet.x + 10,
                        y - 8,
                    );
                    world.addChild(label);
                }
            }

            for (const starbase of intel.starbases) {
                if (starbase.planet_id === null) {
                    continue;
                }

                const planet = planetById.get(starbase.planet_id);
                if (
                    planet === undefined ||
                    planet.x === null ||
                    planet.y === null
                ) {
                    continue;
                }

                const marker = new Graphics()
                    .poly([
                        0, -12,
                        12, 0,
                        0, 12,
                        -12, 0,
                    ])
                    .fill({
                        color: 0xf3c969,
                        alpha: 0.15,
                    })
                    .stroke({
                        color: 0xf3c969,
                        width: 2,
                        alpha: 0.95,
                    });

                marker.position.set(
                    planet.x,
                    renderY(planet.y, bounds),
                );
                marker.eventMode = "static";
                marker.cursor = "pointer";
                marker.on("pointertap", (event) => {
                    event.stopPropagation();
                    onSelect({
                        kind: "starbase",
                        value: starbase,
                    });
                });
                world.addChild(marker);
            }

            for (const ship of intel.ships) {
                if (ship.x === null || ship.y === null) {
                    continue;
                }

                const role = shipRole(ship);
                const marker = shipMarker(
                    role,
                    ownerColor(ship.owner_id),
                );

                marker.position.set(
                    ship.x,
                    renderY(ship.y, bounds),
                );
                marker.eventMode = "static";
                marker.cursor = "pointer";
                marker.on("pointertap", (event) => {
                    event.stopPropagation();
                    onSelect({
                        kind: "ship",
                        value: ship,
                    });
                });
                world.addChild(marker);
            }

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
    }, [bounds, fitViewRef, intel, labelMode, links, onSelect]);

    return <div className="intel-map-canvas-host" ref={hostRef} />;
}


export function PrivateIntelMap({
    intel,
    loading,
    error,
    observerName,
    players,
}: PrivateIntelMapProps) {
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const [labelMode, setLabelMode] = useState<PlanetLabelMode>("name");
    const fitViewRef = useRef<(() => void) | null>(null);

    useEffect(() => {
        setSelected(null);
    }, [intel?.observation.batch_id]);

    if (loading) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Loading observer-specific factual observations…</p>
                    </div>
                </div>
                <div className="intel-map-state">Loading private intelligence…</div>
            </section>
        );
    }

    if (error !== null) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Observer: {observerName}</p>
                    </div>
                </div>
                <div className="intel-map-state intel-map-state-error">
                    {error}
                </div>
            </section>
        );
    }

    if (intel === null) {
        return (
            <section className="panel intel-map-panel">
                <div className="panel-header">
                    <div>
                        <h2>Private intelligence map</h2>
                        <p>Observer: {observerName}</p>
                    </div>
                </div>
                <div className="intel-map-state">
                    No private factual snapshot is stored for this observer and game yet.
                </div>
            </section>
        );
    }

    return (
        <section className="panel intel-map-panel">
            <div className="panel-header intel-map-header">
                <div>
                    <h2>Private intelligence map</h2>
                    <p>
                        Observer: <strong>{intel.observer.planets_username}</strong>
                        {" · "}Turn {intel.turn}
                        {" · "}Observed {formatObservedAt(intel.observation.observed_at)}
                    </p>
                </div>
                <div className="intel-map-actions">
                    <span>{intel.counts.planets} planets</span>
                    <span>{intel.counts.ships} ships</span>
                    <span>{intel.counts.starbases} bases</span>
                    <label className="intel-label-control">
                        <span>Planet labels</span>
                        <select
                            className="secondary-button"
                            onChange={(event) =>
                                setLabelMode(event.target.value as PlanetLabelMode)
                            }
                            value={labelMode}
                        >
                            <option value="none">None</option>
                            <option value="id">Number</option>
                            <option value="name">Name</option>
                        </select>
                    </label>
                    <button
                        className="secondary-button"
                        onClick={() => fitViewRef.current?.()}
                        type="button"
                    >
                        Fit view
                    </button>
                </div>
            </div>

            <div className="intel-map-layout">
                <div className="intel-map-stage-wrap">
                    <PixiMapCanvas
                        fitViewRef={fitViewRef}
                        intel={intel}
                        labelMode={labelMode}
                        onSelect={setSelected}
                    />
                    <div className="intel-map-help">
                        Drag to pan · wheel to zoom · click an entity
                    </div>
                    <div className="intel-map-legend">
                        <span><i className="legend-link" />≤ {PLANET_LINK_RANGE} ly</span>
                        <span><i className="legend-planet" />Planet</span>
                        <span><i className="legend-freighter" />Freighter</span>
                        <span><i className="legend-torpedo" />Torpedo</span>
                        <span><i className="legend-carrier" />Carrier</span>
                        <span><i className="legend-warship" />Combat</span>
                        <span><i className="legend-starbase" />Starbase</span>
                    </div>
                </div>

                <aside className="intel-map-details">
                    <div className="eyebrow">Selected factual observation</div>
                    <EntityDetails
                        players={players}
                        selected={selected}
                    />
                    <div className="intel-provenance-note">
                        <strong>Provenance</strong>
                        <span>
                            linked account #{intel.observer.linked_account_id}
                            {" · "}player slot {intel.observer.player_slot_id}
                        </span>
                        <span>
                            batch #{intel.observation.batch_id}
                            {" · "}{intel.observation.source}
                        </span>
                    </div>
                </aside>
            </div>
        </section>
    );
}
