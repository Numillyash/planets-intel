import { Container, Graphics, Text } from "pixi.js";

import type { SpatialMessageItem } from "../../types/history";
import { renderY, type MapBounds } from "./mapModel";


export interface SpatialMessageSelection {
    positionKey: string;
    x: number;
    y: number;
    messages: SpatialMessageItem[];
}


export function spatialMessagePositionKey(
    item: Pick<SpatialMessageItem, "message_turn" | "x" | "y">,
): string {
    return `${item.message_turn ?? "?"}:${item.x}:${item.y}`;
}


function conciseHeadline(value: string | null): string {
    const normalized = (value ?? "")
        .trim()
        .replace(/\s+/g, " ");
    if (!normalized) return "Message";
    return normalized.length > 30
        ? normalized.slice(0, 27) + "…"
        : normalized;
}


export function drawSpatialMessages({
    world,
    messages,
    bounds,
    selectedPositionKey,
    onSelect,
}: {
    world: Container;
    messages: SpatialMessageItem[];
    bounds: MapBounds;
    selectedPositionKey: string | null;
    onSelect: (selection: SpatialMessageSelection) => void;
}): void {
    const groups = new Map<string, SpatialMessageItem[]>();

    for (const message of messages) {
        const key = spatialMessagePositionKey(message);
        const group = groups.get(key) ?? [];
        group.push(message);
        groups.set(key, group);
    }

    for (const [positionKey, group] of groups) {
        group.sort((left, right) =>
            left.message_key.localeCompare(right.message_key),
        );

        const first = group[0];
        const selected = selectedPositionKey === positionKey;
        const markerY = renderY(first.y, bounds);

        const marker = new Graphics()
            .circle(0, 0, selected ? 9 : 8)
            .fill({
                color: selected ? 0xaedfff : 0x7bbcff,
                alpha: selected ? 0.96 : 0.86,
            })
            .poly([
                -4.5, 7,
                -1.5, 12,
                2, 7.5,
            ])
            .fill({
                color: selected ? 0xaedfff : 0x7bbcff,
                alpha: selected ? 0.96 : 0.86,
            })
            .circle(0, 0, selected ? 12 : 11)
            .stroke({
                color: selected ? 0xf2fbff : 0x286caa,
                width: selected ? 2 : 1.4,
                alpha: 0.96,
            });

        marker.position.set(first.x, markerY);
        marker.eventMode = "static";
        marker.cursor = "pointer";

        const labelText = group.length === 1
            ? conciseHeadline(first.headline)
            : `Messages ×${group.length}`;
        const label = new Text({
            text: labelText,
            style: {
                fill: selected ? 0xe9f8ff : 0x9dd4ff,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 10.5,
                fontWeight: "600",
                stroke: {
                    color: 0x060a10,
                    width: 4,
                },
            },
            resolution: 2,
        });
        label.position.set(first.x + 15, markerY - 7);
        label.eventMode = "none";

        marker.on("pointertap", (pointerEvent) => {
            pointerEvent.stopPropagation();
            onSelect({
                positionKey,
                x: first.x,
                y: first.y,
                messages: group,
            });
        });

        world.addChild(marker);
        world.addChild(label);
    }
}
