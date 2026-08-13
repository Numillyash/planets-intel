import { useEffect, useMemo, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import type {
    CombatEventResultStatus,
    CombatEventSideSummary,
    CombatEventSummary,
} from "../../types/history";


function sideName(side: CombatEventSideSummary): string {
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}


function resultLabel(
    status: CombatEventResultStatus,
    side: CombatEventSideSummary,
): string {
    switch (status) {
        case "survived_post_host":
            return "Survived host · directly observed afterwards";
        case "survived_to_later_combat":
            return "Survived to a later VCR at this position";
        case "defeated":
            return "Defeated in this combat";
        case "planet_held_post_host":
            return `Planet held after host${side.post_host_owner_id !== null ? ` · owner slot ${side.post_host_owner_id}` : ""}`;
        case "planet_owner_changed_post_host":
            return `Planet owner changed after host${side.post_host_owner_id !== null ? ` → slot ${side.post_host_owner_id}` : ""}`;
        default:
            return "Final result not proven by available evidence";
    }
}


function resultColor(status: CombatEventResultStatus): string {
    switch (status) {
        case "survived_post_host":
        case "survived_to_later_combat":
        case "planet_held_post_host":
            return "#82e6b1";
        case "defeated":
            return "#ff9999";
        case "planet_owner_changed_post_host":
            return "#ffd27d";
        default:
            return "#c8d4e4";
    }
}


function eventKind(event: CombatEventSummary): string {
    const shipCount = event.sides.filter(
        (side) => side.object_kind === "ship",
    ).length;
    if (shipCount === 2) return "Ship combat";
    if (shipCount === 1) return "Planet combat";
    return "Combat";
}


function eventTitle(event: CombatEventSummary): string {
    return `${sideName(event.sides[0])} vs ${sideName(event.sides[1])}`;
}


export function CombatEventPanel({
    gameId,
    linkedAccountId,
    turn,
    onFocus,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    onFocus: (event: CombatEventSummary) => void;
}) {
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [selectedEvent, setSelectedEvent] =
        useState<CombatEventSummary | null>(null);
    const [listOpen, setListOpen] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setSelectedEvent(null);

        async function load() {
            try {
                const response = await getHistoricalCombatEvents(
                    gameId,
                    linkedAccountId,
                    turn,
                );
                if (!cancelled) {
                    setEvents(response.events);
                    setError(null);
                }
            } catch (reason) {
                if (!cancelled) {
                    setEvents([]);
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load combat events",
                    );
                }
            }
        }

        void load();
        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    const ordered = useMemo(
        () => [...events].sort((left, right) => left.vcr_id - right.vcr_id),
        [events],
    );

    if (events.length === 0 && error === null) return null;

    return (
        <>
            {listOpen ? (
                <div
                    style={{
                        position: "absolute",
                        zIndex: 5,
                        left: 12,
                        top: 52,
                        width: "min(340px, 46%)",
                        maxHeight: "44%",
                        display: "flex",
                        flexDirection: "column",
                        border: "1px solid rgba(57, 71, 93, 0.78)",
                        borderRadius: 9,
                        background: "rgba(8, 13, 21, 0.94)",
                        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.3)",
                        backdropFilter: "blur(6px)",
                    }}
                >
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 8,
                            padding: "8px 9px",
                            borderBottom: "1px solid rgba(57, 71, 93, 0.6)",
                        }}
                    >
                        <div>
                            <div className="eyebrow">Combat events · T{turn}</div>
                            <strong>{events.length} VCR{events.length === 1 ? "" : "s"}</strong>
                        </div>
                        <button
                            className="secondary-button"
                            onClick={() => setListOpen(false)}
                            style={{ padding: "3px 7px" }}
                            type="button"
                        >
                            Hide
                        </button>
                    </div>

                    {error !== null ? (
                        <div style={{ padding: 9, color: "#ff9999", fontSize: 11 }}>
                            {error}
                        </div>
                    ) : (
                        <div style={{ overflowY: "auto", padding: 6 }}>
                            {ordered.map((event) => {
                                const selected = selectedEvent?.vcr_id === event.vcr_id
                                    && selectedEvent.turn === event.turn;
                                const sourceNames = event.sources
                                    .map((source) => source.planets_username)
                                    .join(", ");

                                return (
                                    <button
                                        className="secondary-button"
                                        key={`${event.turn}:${event.vcr_id}`}
                                        onClick={() => {
                                            setSelectedEvent(event);
                                            onFocus(event);
                                        }}
                                        style={{
                                            width: "100%",
                                            display: "block",
                                            textAlign: "left",
                                            marginBottom: 5,
                                            padding: "7px 8px",
                                            borderColor: selected
                                                ? "rgba(255, 214, 138, 0.9)"
                                                : undefined,
                                            background: selected
                                                ? "rgba(75, 61, 32, 0.6)"
                                                : undefined,
                                        }}
                                        type="button"
                                    >
                                        <strong>VCR #{event.vcr_id} · {eventKind(event)}</strong>
                                        <span
                                            style={{
                                                display: "block",
                                                marginTop: 2,
                                                fontSize: 11,
                                                color: "#c9d4e4",
                                            }}
                                        >
                                            {eventTitle(event)}
                                        </span>
                                        {sourceNames && (
                                            <span
                                                style={{
                                                    display: "block",
                                                    marginTop: 2,
                                                    fontSize: 10,
                                                    color: "#91a9c8",
                                                }}
                                            >
                                                VCR source: {sourceNames}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>
            ) : (
                <button
                    className="secondary-button"
                    onClick={() => setListOpen(true)}
                    style={{
                        position: "absolute",
                        zIndex: 5,
                        left: 12,
                        top: 52,
                    }}
                    type="button"
                >
                    VCRs · {events.length}
                </button>
            )}

            {selectedEvent !== null && (
                <div
                    style={{
                        position: "absolute",
                        zIndex: 6,
                        right: 12,
                        bottom: 12,
                        width: "min(410px, calc(100% - 24px))",
                        maxHeight: "58%",
                        overflowY: "auto",
                        padding: "12px 13px",
                        border: "1px solid rgba(255, 204, 115, 0.55)",
                        borderRadius: 9,
                        background: "rgba(8, 13, 21, 0.97)",
                        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.38)",
                        backdropFilter: "blur(6px)",
                    }}
                >
                    <div
                        style={{
                            display: "flex",
                            alignItems: "flex-start",
                            justifyContent: "space-between",
                            gap: 12,
                        }}
                    >
                        <div>
                            <div className="eyebrow">Combat event</div>
                            <strong>VCR #{selectedEvent.vcr_id} · T{selectedEvent.turn}</strong>
                            <div style={{ color: "#91a9c8", marginTop: 3, fontSize: 12 }}>
                                {eventKind(selectedEvent)}
                                {selectedEvent.sequence_count > 1
                                    ? ` · ${selectedEvent.sequence_index}/${selectedEvent.sequence_count} at this position`
                                    : ""}
                                {selectedEvent.x !== null && selectedEvent.y !== null
                                    ? ` · ${selectedEvent.x}, ${selectedEvent.y}`
                                    : ""}
                            </div>
                            {selectedEvent.sources.length > 0 && (
                                <div style={{ color: "#91a9c8", marginTop: 4, fontSize: 11 }}>
                                    VCR observed via {selectedEvent.sources
                                        .map((source) => source.planets_username)
                                        .join(", ")}
                                </div>
                            )}
                        </div>
                        <button
                            className="secondary-button"
                            onClick={() => setSelectedEvent(null)}
                            style={{ padding: "4px 8px" }}
                            type="button"
                        >
                            Close
                        </button>
                    </div>

                    <div style={{ display: "grid", gap: 8, marginTop: 11 }}>
                        {selectedEvent.sides.map((side) => (
                            <div
                                key={side.side}
                                style={{
                                    padding: "8px 9px",
                                    border: "1px solid rgba(57, 71, 93, 0.72)",
                                    borderRadius: 7,
                                    background: "rgba(13, 20, 31, 0.86)",
                                }}
                            >
                                <strong>{sideName(side)}</strong>
                                <div style={{ color: "#91a9c8", fontSize: 12, marginTop: 3 }}>
                                    {side.object_kind === "ship"
                                        ? `Ship${side.object_id !== null ? ` #${side.object_id}` : ""}${side.hull_id !== null ? ` · hull #${side.hull_id}` : ""}`
                                        : `${side.has_starbase ? "Planet + starbase" : "Planet"}${side.object_id !== null ? ` #${side.object_id}` : ""}`}
                                    {side.owner_id !== null ? ` · VCR owner slot ${side.owner_id}` : ""}
                                </div>
                                <div
                                    style={{
                                        marginTop: 5,
                                        fontSize: 12,
                                        color: resultColor(side.result_status),
                                    }}
                                >
                                    {resultLabel(side.result_status, side)}
                                </div>
                                {side.result_sources.length > 0 && (
                                    <div style={{ color: "#91a9c8", fontSize: 10, marginTop: 3 }}>
                                        Result evidence: {side.result_sources
                                            .map((source) => source.planets_username)
                                            .join(", ")}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    <div
                        style={{
                            color: "#91a9c8",
                            fontSize: 10,
                            lineHeight: 1.45,
                            marginTop: 9,
                        }}
                    >
                        VCR data are factual observations. Result labels are derived at read time
                        from later VCRs at the same position and exact-turn post-host observations;
                        no inferred result is written back into factual intel.
                    </div>
                </div>
            )}
        </>
    );
}
