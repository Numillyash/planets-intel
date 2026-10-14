import { Container, Graphics, Text } from "pixi.js";

import {
    isHostEventReviewedForCurrentRoute,
    markHostEventReviewedForCurrentRoute,
} from "../../lib/hostEventReviewState";
import type { HostEventItem } from "../../types/activity";
import { renderY, type MapBounds } from "./mapModel";


const EXPLOSION_EVENT_TYPE = "ship_explosion_detected";


function normalizedEventLabel(value: string | null): string {
    return (value ?? "")
        .trim()
        .replace(/\s+/g, " ")
        .toLocaleLowerCase();
}


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


/**
 * Presentation identity for one factual host-event notification.
 *
 * Observer/batch provenance is deliberately not part of this key, so multiple
 * observations of the same report render once. Distinct ship names at the same
 * coordinates remain distinct factual events and are only clustered visually.
 */
export function hostEventVisualKey(event: HostEventItem): string {
    return [
        event.event_type,
        event.turn,
        event.x ?? "?",
        event.y ?? "?",
        normalizedEventLabel(event.ship_name),
    ].join(":");
}


function positionKey(event: HostEventItem): string {
    return `${event.turn}:${event.x ?? "?"}:${event.y ?? "?"}`;
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
    const uniqueEvents = new Map<string, HostEventItem>();

    for (const event of events) {
        if (
            event.event_type !== EXPLOSION_EVENT_TYPE
            || event.x === null
            || event.y === null
        ) {
            continue;
        }

        const visualKey = hostEventVisualKey(event);
        if (isHostEventReviewedForCurrentRoute(event.turn, visualKey)) {
            continue;
        }
        if (!uniqueEvents.has(visualKey)) uniqueEvents.set(visualKey, event);
    }

    // Separate factual explosions at the same coordinates are not duplicates.
    // Render one map notification for the location so labels never overlap,
    // while Reports continues to contain every individual explosion fact.
    const groups = new Map<string, HostEventItem[]>();
    for (const event of uniqueEvents.values()) {
        const key = positionKey(event);
        const group = groups.get(key) ?? [];
        group.push(event);
        groups.set(key, group);
    }

    for (const group of groups.values()) {
        group.sort((left, right) =>
            normalizedEventLabel(left.ship_name).localeCompare(
                normalizedEventLabel(right.ship_name),
            ),
        );

        const first = group[0];
        if (first.x === null || first.y === null) continue;

        const selected = group.some((event) => hostEventKey(event) === selectedKey);
        const markerY = renderY(first.y, bounds);

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

        marker.position.set(first.x, markerY);
        marker.eventMode = "static";
        marker.cursor = "pointer";

        const labelText = group.length === 1
            ? first.ship_name
                ? `Explosion · ${first.ship_name}`
                : "Explosion"
            : `Explosions ×${group.length}`;
        const label = new Text({
            text: labelText,
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
        label.position.set(first.x + 16, markerY - 7);
        label.eventMode = "none";

        marker.on("pointertap", (pointerEvent) => {
            pointerEvent.stopPropagation();

            // This is notification state only. Every factual report remains in
            // Reports and provenance; reviewing the cluster merely removes the
            // map notification for its individual explosion reports.
            for (const event of group) {
                markHostEventReviewedForCurrentRoute(
                    event.turn,
                    hostEventVisualKey(event),
                );
            }
            marker.visible = false;
            label.visible = false;
            onSelect(first);
        });

        world.addChild(marker);
        world.addChild(label);
    }
}
