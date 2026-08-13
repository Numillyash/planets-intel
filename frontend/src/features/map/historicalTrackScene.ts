import { Container, Graphics, Text } from "pixi.js";
import type {
    HistoricalCombatEvent,
    HistoricalCombatOutcome,
    HistoricalShipTrack,
    HistoricalShipTrackPoint,
} from "../../types/history";
import { raceVisual } from "../../lib/races";
import { renderY, type MapBounds, type SelectedEntity } from "./mapModel";

export type ShipTrackMode = "off" | "selected" | "all";

const UNKNOWN_TRACK_COLOR = 0x70829a;
const EVENT_SELECT = "dashboard-event-select";

function trackColor(ownerId: number | null): number {
    return raceVisual(ownerId)?.color ?? UNKNOWN_TRACK_COLOR;
}

function requestEventSelection(event: HistoricalCombatEvent) {
    window.dispatchEvent(
        new CustomEvent(EVENT_SELECT, {
            detail: { turn: event.turn, vcrId: event.vcr_id },
        }),
    );
}

function fadedAlpha(
    baseAlpha: number,
    turn: number,
    throughTurn: number,
    fadePerTurn: number,
    minimumAlpha: number,
): number {
    const age = Math.max(throughTurn - turn, 0);
    const retainedPerTurn = Math.min(Math.max(1 - fadePerTurn, 0), 1);
    const alpha = baseAlpha * Math.pow(retainedPerTurn, age);
    return Math.min(Math.max(alpha, minimumAlpha), 1);
}

function combatOutcomeLabel(outcome: HistoricalCombatOutcome | null): string {
    switch (outcome) {
        case "defeated": return "defeated";
        case "survived_to_later_combat": return "survived to later combat";
        default: return "final result unknown";
    }
}

function drawTrackPoint({ world, point, bounds, color, selectedTrack, throughTurn, fadePerTurn }: {
    world: Container;
    point: HistoricalShipTrackPoint;
    bounds: MapBounds;
    color: number;
    selectedTrack: boolean;
    throughTurn: number;
    fadePerTurn: number;
}) {
    const x = point.x;
    const y = renderY(point.y, bounds);
    const isCombat = point.evidence === "combat";
    const alpha = fadedAlpha(
        selectedTrack ? 0.98 : isCombat ? 0.64 : 0.45,
        point.turn,
        throughTurn,
        fadePerTurn,
        selectedTrack ? 0.1 : isCombat ? 0.12 : 0.03,
    );

    if (isCombat) {
        const defeated = point.combat_outcome === "defeated";
        const marker = new Graphics()
            .circle(0, 0, selectedTrack ? 4.6 : 2.7)
            .stroke({
                color: defeated ? 0xff6b6b : color,
                width: selectedTrack ? 1.6 : 0.9,
                alpha,
            });
        marker.position.set(x, y);
        world.addChild(marker);
    } else {
        const marker = new Graphics()
            .circle(0, 0, selectedTrack ? 2.8 : 1.45)
            .fill({ color, alpha });
        if (selectedTrack) {
            marker.stroke({
                color: 0xffffff,
                width: 0.7,
                alpha: fadedAlpha(
                    0.76,
                    point.turn,
                    throughTurn,
                    fadePerTurn,
                    0.08,
                ),
            });
        }
        marker.position.set(x, y);
        world.addChild(marker);
    }

    if (!selectedTrack) return;

    const labelAlpha = fadedAlpha(
        1,
        point.turn,
        throughTurn,
        fadePerTurn,
        0.18,
    );
    const suffix = point.evidence === "combat"
        ? ` · combat · ${combatOutcomeLabel(point.combat_outcome)}${point.combat_vcr_id !== null ? ` #${point.combat_vcr_id}` : ""}`
        : point.gap_from_previous ? " · reacquired" : "";
    const label = new Text({
        text: `T${point.turn}${suffix}`,
        style: {
            fill: point.combat_outcome === "defeated"
                ? 0xff9d9d
                : point.evidence === "combat"
                    ? 0xffd1d1
                    : point.gap_from_previous
                        ? 0xffcf7d
                        : 0xcbd8e8,
            fontFamily: "Inter, Arial, sans-serif",
            fontSize: 9,
            stroke: { color: 0x060a10, width: 3 },
        },
        resolution: 2,
    });
    label.alpha = labelAlpha;
    label.position.set(x + 5, y - 12);
    world.addChild(label);
}

export function drawHistoricalShipTracks({
    world,
    tracks,
    bounds,
    selected,
    mode,
    throughTurn,
    lookbackTurns,
    fadePerTurn,
}: {
    world: Container;
    tracks: HistoricalShipTrack[];
    bounds: MapBounds;
    selected: SelectedEntity | null;
    mode: ShipTrackMode;
    throughTurn: number;
    lookbackTurns: number | null;
    fadePerTurn: number;
}) {
    if (mode === "off") return;

    const selectedShipId = selected?.kind === "ship"
        ? selected.value.ship_id
        : null;
    const minimumTurn = lookbackTurns === null
        ? Number.NEGATIVE_INFINITY
        : throughTurn - Math.max(lookbackTurns, 0);

    for (const track of tracks) {
        const selectedTrack = selectedShipId === track.ship_id;
        if (mode === "selected" && !selectedTrack) continue;

        const points = track.points.filter(
            (point) => point.turn >= minimumTurn && point.turn <= throughTurn,
        );
        if (points.length === 0) continue;

        const color = trackColor(track.owner_id);
        for (let index = 1; index < points.length; index += 1) {
            const previous = points[index - 1];
            const current = points[index];
            if (current.gap_from_previous) continue;

            const line = new Graphics()
                .moveTo(previous.x, renderY(previous.y, bounds))
                .lineTo(current.x, renderY(current.y, bounds))
                .stroke({
                    color,
                    width: selectedTrack ? 2.5 : 1.15,
                    alpha: fadedAlpha(
                        selectedTrack ? 0.94 : 0.34,
                        current.turn,
                        throughTurn,
                        fadePerTurn,
                        selectedTrack ? 0.08 : 0.025,
                    ),
                });
            world.addChild(line);
        }

        for (const point of points) {
            drawTrackPoint({
                world,
                point,
                bounds,
                color,
                selectedTrack,
                throughTurn,
                fadePerTurn,
            });
        }
    }
}

export function combatEventKey(event: HistoricalCombatEvent): string {
    return `${event.turn}:${event.vcr_id}`;
}

interface VcrOnlyContact {
    track: HistoricalShipTrack;
    point: HistoricalShipTrackPoint;
    event: HistoricalCombatEvent;
}

function drawVcrOnlyShipContacts({
    world,
    contacts,
    bounds,
    selectedEventKey,
}: {
    world: Container;
    contacts: VcrOnlyContact[];
    bounds: MapBounds;
    selectedEventKey: string | null;
}) {
    const grouped = new Map<string, VcrOnlyContact[]>();
    for (const contact of contacts) {
        const key = `${contact.point.x}:${contact.point.y}`;
        const group = grouped.get(key) ?? [];
        group.push(contact);
        grouped.set(key, group);
    }

    for (const group of grouped.values()) {
        group.sort((left, right) => left.track.ship_id - right.track.ship_id);

        group.forEach((contact, index) => {
            const centerX = contact.point.x;
            const centerY = renderY(contact.point.y, bounds);
            const count = group.length;
            const angle = Math.PI / 2
                + (Math.PI * 2 * index) / Math.max(count, 1);
            const radius = count > 1 ? 50 : 46;
            const x = centerX + Math.cos(angle) * radius;
            const y = centerY + Math.sin(angle) * radius;
            const color = trackColor(contact.track.owner_id);
            const confirmedBySequence =
                contact.point.combat_outcome === "survived_to_later_combat";
            const evidenceColor = confirmedBySequence ? 0x82e6b1 : 0xffcc73;
            const isSelected = selectedEventKey === combatEventKey(contact.event);

            const connector = new Graphics()
                .moveTo(centerX, centerY)
                .lineTo(x, y)
                .stroke({
                    color: evidenceColor,
                    width: isSelected ? 1.2 : 0.8,
                    alpha: isSelected ? 0.72 : 0.42,
                });
            world.addChild(connector);

            // VCR-only contacts are ships, not combat-event markers. Render a
            // ship-like triangle and keep the outer ring as provenance.
            const marker = new Graphics()
                .moveTo(0, -6)
                .lineTo(5.5, 5)
                .lineTo(-5.5, 5)
                .closePath()
                .fill({ color, alpha: 0.88 })
                .stroke({ color: 0xffffff, width: 0.9, alpha: 0.82 })
                .circle(0, 0, isSelected ? 9.2 : 8.1)
                .stroke({
                    color: isSelected ? 0xffffff : evidenceColor,
                    width: isSelected ? 2.1 : 1.45,
                    alpha: 0.96,
                });
            marker.position.set(x, y);
            marker.eventMode = "static";
            marker.cursor = "pointer";
            marker.on("pointertap", (pointerEvent) => {
                pointerEvent.stopPropagation();
                requestEventSelection(contact.event);
            });
            world.addChild(marker);

            const label = new Text({
                text: `#${contact.track.ship_id}`,
                style: {
                    fill: 0xeaf3ff,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: 9,
                    fontWeight: "600",
                    stroke: { color: 0x060a10, width: 3 },
                },
                resolution: 2,
            });
            label.position.set(x + 10, y - 15);
            world.addChild(label);
        });
    }
}

export function drawCurrentCombatContacts({
    world,
    tracks,
    bounds,
    throughTurn,
    selectedEventKey,
    onSelectEvent,
}: {
    world: Container;
    tracks: HistoricalShipTrack[];
    bounds: MapBounds;
    throughTurn: number;
    selectedEventKey: string | null;
    onSelectEvent: (event: HistoricalCombatEvent) => void;
}) {
    void onSelectEvent;

    const events = new Map<string, HistoricalCombatEvent>();
    const vcrOnlyContacts = new Map<string, VcrOnlyContact>();

    for (const track of tracks) {
        for (const point of track.points) {
            const event = point.combat_event;
            if (
                point.turn !== throughTurn ||
                point.evidence !== "combat" ||
                event === null
            ) {
                continue;
            }

            events.set(combatEventKey(event), event);
            if (!point.has_direct_scan && point.combat_outcome !== "defeated") {
                vcrOnlyContacts.set(
                    `${track.ship_id}:${point.turn}:${point.combat_vcr_id ?? event.vcr_id}`,
                    { track, point, event },
                );
            }
        }
    }

    drawVcrOnlyShipContacts({
        world,
        contacts: [...vcrOnlyContacts.values()],
        bounds,
        selectedEventKey,
    });

    const grouped = new Map<string, HistoricalCombatEvent[]>();
    for (const event of events.values()) {
        if (event.x === null || event.y === null) continue;
        const key = `${event.x}:${event.y}`;
        const group = grouped.get(key) ?? [];
        group.push(event);
        grouped.set(key, group);
    }

    for (const group of grouped.values()) {
        group.sort(
            (left, right) =>
                left.sequence_index - right.sequence_index || left.vcr_id - right.vcr_id,
        );

        group.forEach((event, index) => {
            if (event.x === null || event.y === null) return;

            const centerX = event.x;
            const centerY = renderY(event.y, bounds);
            const count = group.length;
            const angle = -Math.PI / 2
                + (Math.PI * 2 * index) / Math.max(count, 1);
            const offsetRadius = count > 1 ? 34 : 30;
            const x = centerX + Math.cos(angle) * offsetRadius;
            const y = centerY + Math.sin(angle) * offsetRadius;
            const hasDefeated = event.sides.some(
                (side) => side.sequence_status === "defeated",
            );
            const markerColor = hasDefeated ? 0xff8a73 : 0xffcc73;
            const isSelected = selectedEventKey === combatEventKey(event);

            const connector = new Graphics()
                .moveTo(centerX, centerY)
                .lineTo(x, y)
                .stroke({
                    color: markerColor,
                    width: isSelected ? 1.2 : 0.8,
                    alpha: isSelected ? 0.82 : 0.58,
                });
            world.addChild(connector);

            const marker = new Graphics()
                .circle(0, 0, isSelected ? 6.2 : 5.3)
                .fill({ color: 0x111722, alpha: 0.96 })
                .stroke({
                    color: isSelected ? 0xffffff : markerColor,
                    width: isSelected ? 2.3 : 1.7,
                    alpha: 0.98,
                })
                .moveTo(-3.2, 0)
                .lineTo(3.2, 0)
                .moveTo(0, -3.2)
                .lineTo(0, 3.2)
                .stroke({ color: markerColor, width: 1.15, alpha: 0.96 });
            marker.position.set(x, y);
            marker.eventMode = "static";
            marker.cursor = "pointer";
            marker.on("pointertap", (pointerEvent) => {
                pointerEvent.stopPropagation();
                requestEventSelection(event);
            });
            world.addChild(marker);
        });
    }
}
