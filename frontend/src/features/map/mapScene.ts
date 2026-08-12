import { Container, Graphics, Text } from "pixi.js";
import type { LatestPrivateIntelResponse } from "../../types/api";
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



function shipMarker(
    role: ShipRole,
    color: number,
    compact = false,
): Graphics {
    const marker = new Graphics();
    const radius = compact ? 5.5 : 7.5;

    if (role === "freighter") {
        marker.rect(-radius, -radius, radius * 2, radius * 2);
    } else if (role === "carrier") {
        marker.poly([
            0, -radius - 1,
            radius, -radius * 0.45,
            radius, radius * 0.45,
            0, radius + 1,
            -radius, radius * 0.45,
            -radius, -radius * 0.45,
        ]);
    } else if (role === "torpedo") {
        marker.poly([
            0, -radius - 1,
            radius, radius,
            -radius, radius,
        ]);
    } else {
        marker.poly([
            0, -radius - 1,
            radius, 0,
            0, radius + 1,
            -radius, 0,
        ]);
    }

    marker
        .fill({ color, alpha: 0.96 })
        .stroke({
            color: 0xffffff,
            width: compact ? 0.8 : 1,
            alpha: 0.72,
        });

    return marker;
}



export function drawMapScene({
    world,
    intel,
    bounds,
    links,
    shipPositions,
    basesByPlanet,
    labelMode,
    onSelect,
}: {
    world: Container;
    intel: LatestPrivateIntelResponse;
    bounds: MapBounds;
    links: PlanetLink[];
    shipPositions: ShipVisualPosition[];
    basesByPlanet: Map<number, LatestPrivateIntelResponse["starbases"][number]>;
    labelMode: PlanetLabelMode;
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
    
    const orbitSpokes = new Graphics();
    for (const position of shipPositions) {
        if (
            position.x === position.anchorX &&
            position.y === position.anchorY
        ) {
            continue;
        }
        orbitSpokes
            .moveTo(position.anchorX, position.anchorY)
            .lineTo(position.x, position.y);
    }
    orbitSpokes.stroke({
        color: 0x63748c,
        width: 0.7,
        alpha: 0.36,
    });
    world.addChild(orbitSpokes);
    
    for (const planet of intel.planets) {
        if (planet.x === null || planet.y === null) {
            continue;
        }
    
        const y = renderY(planet.y, bounds);
        const orbitShips = shipsAtPlanet(intel.ships, planet);
        const starbase = basesByPlanet.get(planet.planet_id) ?? null;
    
        if (orbitShips.length > 0) {
            const orbitRing = new Graphics()
                .circle(0, 0, PLANET_RADIUS + 5)
                .stroke({
                    color: 0x8fa2bb,
                    width: 1.2,
                    alpha: 0.72,
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
    
        const labelText = planetLabel(planet, labelMode);
        if (labelText !== null) {
            const label = new Text({
                text: labelText,
                style: {
                    fill: 0xc1ccda,
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
    
    for (const position of shipPositions) {
        const role = shipRole(position.ship);
        const inOrbit = position.planetId !== null;
        const marker = shipMarker(
            role,
            ownerColor(position.ship.owner_id),
            inOrbit,
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
