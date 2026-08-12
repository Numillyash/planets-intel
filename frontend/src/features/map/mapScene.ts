import { Container, Graphics, Text } from "pixi.js";
import type { PlanetObservationResponse } from "../../types/api";
import type {
    MapStarbaseObservation,
    PrivateIntelMapResponse,
} from "../../types/intel";
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
    if (selected === null) {
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
        // At-planet ships are intentionally not drawn as separate glyphs.
        // The orbit ring signals their presence, and the planet Orbit panel
        // remains the factual selector for individual ships.
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
