import { Container, Graphics, Text } from "pixi.js";

import type { HostEventItem } from "../../types/activity";
import { renderY, type MapBounds } from "./mapModel";


const EXPLOSION_EVENT_TYPE = "ship_explosion_detected";


export function hostEventKey(event: HostEventItem): string {
    return [
        event.event_type,
        event.turn,
        event.x ?? "?",
        event.y ?? "?",
        event.ship_name ?? "?",
        event.summary,
    ].join(":");
}


export function drawHostEvents({
    world,
    events,
    bounds,
    selectedKey,
    onSelect,
}: {
    world: Container;
    events: HostEventItem[];
    bounds: MapBounds;
    selectedKey: string | null;
    onSelect: (event: HostEventItem) => void;
}): void {
    for (const event of events) {
        if (
            event.event_type !== EXPLOSION_EVENT_TYPE
            || event.x === null
            || event.y === null
        ) {
            continue;
        }

        const key = hostEventKey(event);
        const selected = key === selectedKey;
        const markerY = renderY(event.y, bounds);

        const marker = new Graphics()
            .circle(0, 0, selected ? 5.5 : 4.5)
            .fill({ color: 0xffbd59, alpha: 0.98 })
            .circle(0, 0, selected ? 12 : 10)
            .stroke({
                color: selected ? 0xfff0b5 : 0xff5f67,
                width: selected ? 2.2 : 1.6,
                alpha: 0.98,
            })
            .moveTo(-14, 0)
            .lineTo(14, 0)
            .moveTo(0, -14)
            .lineTo(0, 14)
            .moveTo(-9.5, -9.5)
            .lineTo(9.5, 9.5)
            .moveTo(9.5, -9.5)
            .lineTo(-9.5, 9.5)
            .stroke({
                color: selected ? 0xfff0b5 : 0xff6570,
                width: selected ? 1.9 : 1.25,
                alpha: 0.95,
            });

        marker.position.set(event.x, markerY);
        marker.eventMode = "static";
        marker.cursor = "pointer";
        marker.on("pointertap", (pointerEvent) => {
            pointerEvent.stopPropagation();
            onSelect(event);
        });
        world.addChild(marker);

        const label = new Text({
            text: event.ship_name
                ? `Explosion · ${event.ship_name}`
                : "Explosion",
            style: {
                fill: selected ? 0xfff0b5 : 0xffa9ae,
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
        label.position.set(event.x + 16, markerY - 7);
        label.eventMode = "none";
        world.addChild(label);
    }
}
