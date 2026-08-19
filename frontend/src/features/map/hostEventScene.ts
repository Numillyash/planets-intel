import { Container, Graphics, Text } from "pixi.js";

import {
    isHostEventReviewedForCurrentRoute,
    markHostEventReviewedForCurrentRoute,
} from "../../lib/hostEventReviewState";
import type { HostEventItem } from "../../types/activity";
import { hasCurrentCombatPosition } from "./currentCombatMapRegistry";
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
 * Presentation identity for a map notification.
 *
 * Host-event provenance may legitimately contain several observations of the
 * same incident. The map must not render those observer copies on top of each
 * other, so the visual key intentionally ignores source/batch metadata and the
 * generated summary text while retaining the factual incident coordinates and
 * ship name.
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
    const renderedVisualKeys = new Set<string>();

    for (const event of events) {
        if (
            event.event_type !== EXPLOSION_EVENT_TYPE
            || event.x === null
            || event.y === null
        ) {
            continue;
        }

        const visualKey = hostEventVisualKey(event);
        if (renderedVisualKeys.has(visualKey)) {
            continue;
        }
        renderedVisualKeys.add(visualKey);

        if (isHostEventReviewedForCurrentRoute(event.turn, visualKey)) {
            continue;
        }

        // Combat VCR and long-range explosion reports are separate factual
        // evidence, but rendering both at the same current-turn coordinate
        // produces two competing map controls for one incident. The VCR owns
        // the actionable map marker; the report remains available in Reports.
        if (hasCurrentCombatPosition(event.turn, event.x, event.y)) {
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

        marker.on("pointertap", (pointerEvent) => {
            pointerEvent.stopPropagation();

            // Map review state is presentation-only. Keep the factual report
            // in history/Reports, but remove its notification immediately and
            // remember that choice across a reload for this game + turn.
            markHostEventReviewedForCurrentRoute(event.turn, visualKey);
            marker.visible = false;
            label.visible = false;
            onSelect(event);
        });

        world.addChild(marker);
        world.addChild(label);
    }
}
