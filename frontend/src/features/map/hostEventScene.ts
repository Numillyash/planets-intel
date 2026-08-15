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
            event.event_type !== EXPLOSION_EVENT_TYPE ||
            event.x === null ||
            event.y === null
        ) {
            continue;
        }

        const key = hostEventKey(event);
        const selected = key === selectedKey;
        const y = renderY(event.y, bounds);
        const marker = new Graphics();

        marker
            .circle(0, 0, selected ? 6.5 : 5.5)
            .fill({ color: 0xffb24a, alpha: 0.96 })
            .circle(0, 0, selected ? 13 : 11)
            .stroke({
                color: selected ? 0xfff2b8 : 0xff6b57,
                width: selected ? 2.2 : 1.6,
                alpha: 0.95,
            })
            .moveTo(-15, 0)
            .lineTo(15, 0)
            .moveTo(0, -15)
            .lineTo(0, 15)
            .moveTo(-10, -10)
            .lineTo(10, 10)
            .moveTo(10, -10)
            .lineTo(-10, 10)
            .stroke({
                color: 0xff6b57,
                width: selected ? 2 : 1.35,
                alpha: 0.92,
            });

        marker.position.set(event.x, y);
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
                fill: selected ? 0xfff2b8 : 0xffb3a7,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 11,
                fontWeight: "600",
                stroke: {
                    color: 0x060a10,
                    width: 4,
                },
            },
            resolution: 2,
        });
        label.position.set(event.x + 17, y - 8);
        label.eventMode = "none";
        world.addChild(label);
    }
}
