import { useEffect, useState } from "react";
import { getPlayerActivity } from "../../api/activity";
import type { PlayerActivityItem } from "../../types/activity";

function localTime(minute: number | null): string {
    if (minute === null) return "learning";
    const value = new Date();
    value.setUTCHours(0, minute, 0, 0);
    return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function PlayerActivityPanel(props: { gameId: number; throughTurn: number }) {
    const [items, setItems] = useState<PlayerActivityItem[]>([]);
    const [open, setOpen] = useState(false);

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

    if (!open) {
        return <button className="secondary-button" onClick={() => setOpen(true)} type="button">Player activity · {items.length}</button>;
    }

    return (
        <div style={{ maxHeight: 260, overflowY: "auto", padding: 8, border: "1px solid rgba(57,71,93,.78)", borderRadius: 8, background: "rgba(8,13,21,.96)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <div><div className="eyebrow">Player activity · T{props.throughTurn}</div><strong>Observed timing</strong></div>
                <button className="secondary-button" onClick={() => setOpen(false)} style={{ padding: "3px 7px" }} type="button">Hide</button>
            </div>
            {items.filter((item) => item.current_state !== "dead").map((item) => {
                const minute = item.typical_open_utc_minute ?? item.typical_ready_utc_minute;
                return (
                    <div key={item.slot_id} style={{ marginTop: 7, paddingTop: 6, borderTop: "1px solid rgba(57,71,93,.5)", fontSize: 11 }}>
                        <strong>{item.username}</strong> · {item.current_state}
                        <div style={{ color: "#91a9c8", marginTop: 2 }}>
                            likely activity ~{localTime(minute)} · {item.prediction_confidence}
                        </div>
                        <div style={{ color: "#7187a4", marginTop: 1 }}>
                            {item.open_samples} open · {item.ready_samples} ready samples
                        </div>
                    </div>
                );
            })}
            <div style={{ color: "#7187a4", fontSize: 10, marginTop: 8 }}>
                Open time is first observed within the polling interval; Ready uses turnreadydate when available. This estimates game activity, not continuous online presence.
            </div>
        </div>
    );
}
