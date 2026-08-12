import { Container, Graphics, Text } from "pixi.js";
import { raceVisual } from "../../lib/races";
import type { PrivateIntelMapResponse } from "../../types/intel";
import {
    renderY,
    type MapBounds,
    type SelectedEntity,
} from "./mapModel";
import {
    minefieldIsWeb,
    minefieldOwnerId,
    minefieldSourcePlanet,
} from "./minefieldAnalysis";

const UNKNOWN_MINE_COLOR = 0x98a6b8;
const WEB_MINE_COLOR = 0xb66dff;

export function drawMinefields({
    world,
    intel,
    bounds,
    selected,
    onSelect,
}: {
    world: Container;
    intel: PrivateIntelMapResponse;
    bounds: MapBounds;
    selected: SelectedEntity | null;
    onSelect: (entity: SelectedEntity) => void;
}) {
    for (const feature of intel.stellar_cartography) {
        if (
            feature.feature_type !== "minefield" ||
            feature.x === null ||
            feature.y === null ||
            feature.radius === null ||
            feature.radius <= 0
        ) {
            continue;
        }

        const ownerId = minefieldOwnerId(feature);
        const web = minefieldIsWeb(feature);
        const color = web
            ? WEB_MINE_COLOR
            : raceVisual(ownerId)?.color ?? UNKNOWN_MINE_COLOR;
        const isSelected =
            selected?.kind === "stellar" &&
            selected.value.feature_type === "minefield" &&
            selected.value.feature_id === feature.feature_id;
        const y = renderY(feature.y, bounds);

        const field = new Graphics()
            .circle(0, 0, feature.radius)
            .fill({ color, alpha: web ? 0.045 : 0.028 })
            .stroke({
                color: isSelected ? 0xffffff : color,
                width: isSelected ? 2.1 : 1.15,
                alpha: isSelected ? 0.94 : 0.55,
            });
        field.position.set(feature.x, y);
        field.eventMode = "static";
        field.cursor = "pointer";
        field.on("pointertap", (event) => {
            event.stopPropagation();
            onSelect({ kind: "stellar", value: feature });
        });
        world.addChild(field);

        const center = new Graphics()
            .circle(0, 0, 2.4)
            .fill({ color, alpha: 0.9 });
        center.position.set(feature.x, y);
        world.addChild(center);

        if (!isSelected) {
            continue;
        }

        const label = new Text({
            text: `${web ? "Web minefield" : "Minefield"} #${feature.feature_id}`,
            style: {
                fill: 0xf3f7ff,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 12,
                fontWeight: "600",
                stroke: { color: 0x060a10, width: 4 },
            },
            resolution: 2,
        });
        label.position.set(feature.x + 10, y - 18);
        world.addChild(label);

        const source = minefieldSourcePlanet(intel, feature);
        if (
            source?.planet.x !== null &&
            source?.planet.y !== null &&
            source !== null
        ) {
            const sourceY = renderY(source.planet.y, bounds);
            const guide = new Graphics()
                .moveTo(feature.x, y)
                .lineTo(source.planet.x, sourceY)
                .stroke({
                    color,
                    width: 1.3,
                    alpha: 0.72,
                });
            world.addChild(guide);

            const sourceHalo = new Graphics()
                .circle(0, 0, 13)
                .stroke({
                    color,
                    width: 2.2,
                    alpha: 0.96,
                });
            sourceHalo.position.set(source.planet.x, sourceY);
            world.addChild(sourceHalo);
        }
    }
}
