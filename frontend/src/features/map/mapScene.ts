import { Container, Graphics, Text } from "pixi.js";
import type { PlanetObservationResponse } from "../../types/api";
import type {
    MapStarbaseObservation,
    MapStellarCartographyObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
import { raceVisual } from "../../lib/races";
import {
    PLANET_RADIUS,
    planetLabel,
    renderY,
    shipRole,
    shipsAtPlanet,
    type MapBounds,
    type PlanetLabelMode,
    type PlanetLink,
    type SelectedEntity,
    type ShipRole,
    type ShipVisualPosition,
} from "./mapModel";
import {
    analyzeRouteRadiation,
    shipHistoryRoute,
    shipPlannedRoute,
    type MapPoint,
} from "./navigationAnalysis";


const UNKNOWN_OWNER_COLOR = 0x7b8798;


function ownerColor(ownerId: number | null): number {
    return raceVisual(ownerId)?.color ?? UNKNOWN_OWNER_COLOR;
}


function payloadNumber(
    feature: MapStellarCartographyObservation,
    key: string,
): number | null {
    const value = feature.payload[key];
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : null;
}


function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
}


function starClusterColor(temperature: number | null): number {
    if (temperature === null) return 0xd7e4f5;
    if (temperature <= 3000) return 0xef5a4f;
    if (temperature <= 6000) return 0xf0cf55;
    if (temperature <= 10000) return 0xa97855;
    if (temperature <= 20000) return 0xf2f3e9;
    return 0x86bfff;
}


function featureIsSelected(
    selected: SelectedEntity | null,
    feature: MapStellarCartographyObservation,
): boolean {
    return selected?.kind === "stellar" &&
        selected.value.feature_type === feature.feature_type &&
        selected.value.feature_id === feature.feature_id;
}


function addSelectedFeatureLabel(
    world: Container,
    feature: MapStellarCartographyObservation,
    x: number,
    y: number,
) {
    const kindLabel = feature.feature_type === "nebula"
        ? "Nebula"
        : feature.feature_type === "ion_storm"
            ? "Ion storm"
            : "Star cluster";

    const label = new Text({
        text: feature.name ?? `${kindLabel} #${feature.feature_id}`,
        style: {
            fill: 0xf4f8ff,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 12,
            fontWeight: "600",
            stroke: {
                color: 0x060a10,
                width: 4,
            },
        },
        resolution: 2,
    });
    label.position.set(x + 10, y - 16);
    world.addChild(label);
}


function drawNebula(
    world: Container,
    feature: MapStellarCartographyObservation,
    bounds: MapBounds,
    selected: SelectedEntity | null,
    onSelect: (entity: SelectedEntity) => void,
) {
    if (feature.x === null || feature.y === null || feature.radius === null) {
        return;
    }

    const y = renderY(feature.y, bounds);
    const intensity = payloadNumber(feature, "intensity") ?? 0;
    const alpha = 0.07 + clamp(intensity / 100, 0, 1) * 0.08;
    const isSelected = featureIsSelected(selected, feature);

    const cloud = new Graphics()
        .circle(0, 0, feature.radius)
        .fill({ color: 0x3f7fae, alpha })
        .stroke({
            color: isSelected ? 0xaedfff : 0x5c9cca,
            width: isSelected ? 2 : 1,
            alpha: isSelected ? 0.9 : 0.32,
        });

    cloud.circle(0, 0, feature.radius * 0.72).stroke({
        color: 0x76b5da,
        width: 1,
        alpha: 0.12,
    });
    cloud.circle(0, 0, feature.radius * 0.42).stroke({
        color: 0x91c8e6,
        width: 1,
        alpha: 0.09,
    });

    cloud.position.set(feature.x, y);
    cloud.eventMode = "static";
    cloud.cursor = "pointer";
    cloud.on("pointertap", (event) => {
        event.stopPropagation();
        onSelect({ kind: "stellar", value: feature });
    });
    world.addChild(cloud);

    if (isSelected) {
        addSelectedFeatureLabel(world, feature, feature.x, y);
    }
}


function drawStarCluster(
    world: Container,
    feature: MapStellarCartographyObservation,
    bounds: MapBounds,
    selected: SelectedEntity | null,
    onSelect: (entity: SelectedEntity) => void,
) {
    if (feature.x === null || feature.y === null || feature.radius === null) {
        return;
    }

    const y = renderY(feature.y, bounds);
    const mass = payloadNumber(feature, "mass");
    const temperature = payloadNumber(feature, "temp");
    const haloRadius = mass !== null && mass > 0
        ? Math.sqrt(mass)
        : feature.radius;
    const color = starClusterColor(temperature);
    const isSelected = featureIsSelected(selected, feature);

    const halo = new Graphics()
        .circle(0, 0, haloRadius)
        .fill({ color, alpha: 0.045 })
        .stroke({
            color,
            width: isSelected ? 2 : 1.1,
            alpha: isSelected ? 0.78 : 0.25,
        });
    halo.position.set(feature.x, y);
    world.addChild(halo);

    const core = new Graphics()
        .circle(0, 0, feature.radius)
        .fill({ color, alpha: 0.45 })
        .stroke({
            color: isSelected ? 0xffffff : color,
            width: isSelected ? 2.2 : 1.4,
            alpha: 0.92,
        });
    core.position.set(feature.x, y);
    core.eventMode = "static";
    core.cursor = "pointer";
    core.on("pointertap", (event) => {
        event.stopPropagation();
        onSelect({ kind: "stellar", value: feature });
    });
    world.addChild(core);

    if (isSelected) {
        addSelectedFeatureLabel(world, feature, feature.x, y);
    }
}


function drawIonStorm(
    world: Container,
    feature: MapStellarCartographyObservation,
    bounds: MapBounds,
    selected: SelectedEntity | null,
    onSelect: (entity: SelectedEntity) => void,
) {
    if (feature.x === null || feature.y === null || feature.radius === null) {
        return;
    }

    const y = renderY(feature.y, bounds);
    const voltage = payloadNumber(feature, "voltage") ?? 0;
    const heading = payloadNumber(feature, "heading");
    const warp = payloadNumber(feature, "warp") ?? 0;
    const isGrowing = feature.payload.isgrowing === true;
    const isSelected = featureIsSelected(selected, feature);
    const alpha = 0.07 + clamp(voltage / 300, 0, 1) * 0.13;

    const storm = new Graphics()
        .circle(0, 0, feature.radius)
        .fill({ color: 0xe7bd3d, alpha })
        .stroke({
            color: isSelected ? 0xffef9a : 0xe8c95d,
            width: isSelected ? 2 : 1.1,
            alpha: isSelected ? 0.9 : 0.48,
        });

    storm.circle(0, 0, feature.radius * 0.68).stroke({
        color: 0xf2d96b,
        width: 1,
        alpha: isGrowing ? 0.28 : 0.15,
    });

    storm.position.set(feature.x, y);
    storm.eventMode = "static";
    storm.cursor = "pointer";
    storm.on("pointertap", (event) => {
        event.stopPropagation();
        onSelect({ kind: "stellar", value: feature });
    });
    world.addChild(storm);

    const center = new Graphics()
        .circle(0, 0, 2.4)
        .fill({ color: 0xffdf62, alpha: 0.9 });
    center.position.set(feature.x, y);
    world.addChild(center);

    if (heading !== null && warp > 0) {
        const angle = heading * Math.PI / 180;
        const length = 14 + Math.min(warp, 20) * 4;
        const dx = Math.sin(angle) * length;
        const dy = -Math.cos(angle) * length;
        const vector = new Graphics()
            .moveTo(feature.x, y)
            .lineTo(feature.x + dx, y + dy)
            .stroke({
                color: 0xffd95c,
                width: 1.3,
                alpha: 0.8,
            });
        world.addChild(vector);
    }

    if (isSelected) {
        addSelectedFeatureLabel(world, feature, feature.x, y);
    }
}


function drawStellarCartography(
    world: Container,
    intel: PrivateIntelMapResponse,
    bounds: MapBounds,
    selected: SelectedEntity | null,
    onSelect: (entity: SelectedEntity) => void,
) {
    for (const feature of intel.stellar_cartography) {
        if (feature.feature_type === "nebula") {
            drawNebula(world, feature, bounds, selected, onSelect);
        } else if (feature.feature_type === "star_cluster") {
            drawStarCluster(world, feature, bounds, selected, onSelect);
        } else if (feature.feature_type === "ion_storm") {
            drawIonStorm(world, feature, bounds, selected, onSelect);
        }
    }
}


function shipMarker(role: ShipRole, color: number): Graphics {
    const marker = new Graphics();
    const radius = 4.1;

    if (role === "freighter") {
        marker.rect(-radius, -radius, radius * 2, radius * 2);
    } else if (role === "carrier") {
        marker.poly([
            0, -radius - 0.8,
            radius, -radius * 0.45,
            radius, radius * 0.45,
            0, radius + 0.8,
            -radius, radius * 0.45,
            -radius, -radius * 0.45,
        ]);
    } else if (role === "torpedo") {
        marker.poly([
            0, -radius - 0.8,
            radius, radius,
            -radius, radius,
        ]);
    } else {
        marker.poly([
            0, -radius - 0.8,
            radius, 0,
            0, radius + 0.8,
            -radius, 0,
        ]);
    }

    marker
        .fill({ color, alpha: 0.96 })
        .stroke({
            color: 0xffffff,
            width: 0.8,
            alpha: 0.68,
        });

    return marker;
}


function planetIsSelected(
    selected: SelectedEntity | null,
    planet: PlanetObservationResponse,
): boolean {
    if (selected === null || selected.kind === "stellar") {
        return false;
    }

    if (selected.kind === "planet") {
        return selected.value.planet_id === planet.planet_id;
    }

    if (selected.kind === "starbase") {
        return selected.value.planet_id === planet.planet_id;
    }

    return (
        planet.x !== null &&
        planet.y !== null &&
        selected.value.x === planet.x &&
        selected.value.y === planet.y
    );
}


function drawRouteLine(
    world: Container,
    route: MapPoint[],
    bounds: MapBounds,
    color: number,
    alpha: number,
    width: number,
) {
    if (route.length < 2) {
        return;
    }

    const path = new Graphics();
    path.moveTo(route[0].x, renderY(route[0].y, bounds));

    for (let index = 1; index < route.length; index += 1) {
        path.lineTo(route[index].x, renderY(route[index].y, bounds));
    }

    path.stroke({ color, alpha, width });
    world.addChild(path);
}


function drawSelectedShipTrajectory(
    world: Container,
    intel: PrivateIntelMapResponse,
    bounds: MapBounds,
    selected: SelectedEntity | null,
) {
    if (selected?.kind !== "ship") {
        return;
    }

    const history = shipHistoryRoute(selected.value);
    const planned = shipPlannedRoute(selected.value);

    drawRouteLine(world, history, bounds, 0x8795aa, 0.32, 1.2);
    drawRouteLine(world, planned, bounds, 0x62d8ff, 0.92, 2);

    if (planned.length >= 2) {
        for (const waypoint of planned.slice(1)) {
            const marker = new Graphics()
                .circle(0, 0, 3.2)
                .fill({ color: 0x62d8ff, alpha: 0.9 })
                .stroke({ color: 0xe8f8ff, width: 0.8, alpha: 0.8 });
            marker.position.set(waypoint.x, renderY(waypoint.y, bounds));
            world.addChild(marker);
        }
    }

    const radiation = analyzeRouteRadiation(intel, planned);
    if (radiation.closestPoint !== null && (
        radiation.coreCrossing || radiation.maxRadiation > 0
    )) {
        const danger = new Graphics()
            .circle(0, 0, radiation.coreCrossing ? 6 : 4.5)
            .stroke({
                color: radiation.coreCrossing ? 0xff566b : 0xffb347,
                width: 2,
                alpha: 0.95,
            });
        danger.position.set(
            radiation.closestPoint.x,
            renderY(radiation.closestPoint.y, bounds),
        );
        world.addChild(danger);
    }
}


export function drawMapScene({
    world,
    intel,
    bounds,
    links,
    shipPositions,
    basesByPlanet,
    labelMode,
    selected,
    onSelect,
}: {
    world: Container;
    intel: PrivateIntelMapResponse;
    bounds: MapBounds;
    links: PlanetLink[];
    shipPositions: ShipVisualPosition[];
    basesByPlanet: Map<number, MapStarbaseObservation>;
    labelMode: PlanetLabelMode;
    selected: SelectedEntity | null;
    onSelect: (entity: SelectedEntity) => void;
}) {
    drawStellarCartography(
        world,
        intel,
        bounds,
        selected,
        onSelect,
    );

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
        alpha: 0.42,
    });
    world.addChild(linkLayer);

    drawSelectedShipTrajectory(world, intel, bounds, selected);

    for (const planet of intel.planets) {
        if (planet.x === null || planet.y === null) {
            continue;
        }

        const y = renderY(planet.y, bounds);
        const orbitShips = shipsAtPlanet(intel.ships, planet);
        const starbase = basesByPlanet.get(planet.planet_id) ?? null;
        const isSelected = planetIsSelected(selected, planet);

        if (isSelected) {
            const selectionHalo = new Graphics()
                .circle(0, 0, PLANET_RADIUS + 8)
                .stroke({
                    color: 0xe8f3ff,
                    width: 2,
                    alpha: 0.96,
                });
            selectionHalo.position.set(planet.x, y);
            world.addChild(selectionHalo);
        }

        if (orbitShips.length > 0) {
            const orbitRing = new Graphics()
                .circle(0, 0, PLANET_RADIUS + 4.5)
                .stroke({
                    color: isSelected ? 0xb7d8ff : 0x8fa2bb,
                    width: isSelected ? 1.6 : 1.1,
                    alpha: isSelected ? 0.94 : 0.68,
                });
            orbitRing.position.set(planet.x, y);
            world.addChild(orbitRing);
        }

        const marker = new Graphics();
        if (starbase !== null) {
            marker.rect(
                -PLANET_RADIUS,
                -PLANET_RADIUS,
                PLANET_RADIUS * 2,
                PLANET_RADIUS * 2,
            );
        } else {
            marker.circle(0, 0, PLANET_RADIUS);
        }

        marker
            .fill(ownerColor(planet.owner_id))
            .stroke({
                color: starbase !== null ? 0xf3c969 : 0xf4f7fb,
                width: starbase !== null ? 1.8 : 1.2,
                alpha: starbase !== null ? 0.95 : 0.58,
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

        const normalLabel = planetLabel(planet, labelMode);
        const labelText = normalLabel ?? (
            isSelected
                ? planet.name ?? `#${planet.planet_id}`
                : null
        );

        if (labelText !== null) {
            const label = new Text({
                text: labelText,
                style: {
                    fill: isSelected ? 0xf5f9ff : 0xc1ccda,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: isSelected ? 12 : 11,
                    fontWeight: isSelected ? "600" : "400",
                    stroke: {
                        color: 0x060a10,
                        width: isSelected ? 4 : 3,
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

    for (const position of shipPositions) {
        if (position.planetId !== null) {
            continue;
        }

        const role = shipRole(position.ship);
        const isSelected = (
            selected?.kind === "ship" &&
            selected.value.ship_id === position.ship.ship_id
        );

        if (isSelected) {
            const halo = new Graphics()
                .circle(0, 0, 8)
                .stroke({
                    color: 0xe8f3ff,
                    width: 1.6,
                    alpha: 0.96,
                });
            halo.position.set(position.x, position.y);
            world.addChild(halo);
        }

        const marker = shipMarker(
            role,
            ownerColor(position.ship.owner_id),
        );

        marker.position.set(position.x, position.y);
        marker.eventMode = "static";
        marker.cursor = "pointer";
        marker.on("pointertap", (event) => {
            event.stopPropagation();
            onSelect({
                kind: "ship",
                value: position.ship,
            });
        });
        world.addChild(marker);
    }
}
