import { useEffect, useState } from "react";
import { getPlayerActivity } from "../../api/activity";
import type { PlayerActivityItem } from "../../types/activity";

function localTime(minute: number | null): string {
    if (minute === null) return "learning";
    const value = new Date();
    value.setUTCHours(0, minute, 0, 0);
    return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function PlayerActivityPanel(props: {
    gameId: number;
    throughTurn: number;
    embedded?: boolean;
}) {
    const [items, setItems] = useState<PlayerActivityItem[]>([]);
    const [open, setOpen] = useState(props.embedded ?? false);

    useEffect(() => {
        if (props.embedded) setOpen(true);
    }, [props.embedded]);

    useEffect(() => {
        let active = true;
        async function load() {
            try {
                const data = await getPlayerActivity(props.gameId, props.throughTurn);
                if (active) setItems(data.players);
            } catch {
                if (active) setItems([]);
            }
        }
        void load();
        const timer = window.setInterval(() => void load(), 5 * 60 * 1000);
        return () => { active = false; window.clearInterval(timer); };
    }, [props.gameId, props.throughTurn]);

    if (!open && !props.embedded) {
        return (
            <button
                className="secondary-button"
                onClick={() => setOpen(true)}
                type="button"
            >
                Player activity · {items.length}
            </button>
        );
    }

    const visibleItems = items.filter((item) => item.current_state !== "dead");

    return (
        <section className={props.embedded ? "panel dashboard-embedded-panel" : undefined}>
            <div
                style={{
                    maxHeight: props.embedded ? "none" : 260,
                    overflowY: "auto",
                    padding: props.embedded ? 0 : 8,
                    border: props.embedded ? 0 : "1px solid rgba(57,71,93,.78)",
                    borderRadius: props.embedded ? 0 : 8,
                    background: props.embedded ? "transparent" : "rgba(8,13,21,.96)",
                }}
            >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <div>
                        <div className="eyebrow">Turn status · T{props.throughTurn}</div>
                        <strong>Player activity and readiness</strong>
                    </div>
                    {!props.embedded && (
                        <button
                            className="secondary-button"
                            onClick={() => setOpen(false)}
                            style={{ padding: "3px 7px" }}
                            type="button"
                        >
                            Hide
                        </button>
                    )}
                </div>

                {visibleItems.length === 0 ? (
                    <p className="subtitle" style={{ marginTop: 10 }}>
                        No activity samples are available yet.
                    </p>
                ) : (
                    <div className="dashboard-activity-grid">
                        {visibleItems.map((item) => {
                            const minute = item.typical_open_utc_minute
                                ?? item.typical_ready_utc_minute;
                            return (
                                <div className="dashboard-activity-card" key={item.slot_id}>
                                    <div>
                                        <strong>{item.username}</strong>
                                        <span>{item.current_state}</span>
                                    </div>
                                    <small>
                                        likely activity ~{localTime(minute)} · {item.prediction_confidence}
                                    </small>
                                    <small>
                                        {item.open_samples} open · {item.ready_samples} ready samples
                                    </small>
                                </div>
                            );
                        })}
                    </div>
                )}

                <div style={{ color: "#7187a4", fontSize: 10, marginTop: 10 }}>
                    Open time is first observed within the polling interval; Ready uses turnreadydate when available. This estimates game activity, not continuous online presence.
                </div>
            </div>
        </section>
    );
}
