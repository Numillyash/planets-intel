import { useEffect, useState } from "react";
import { getHostEvents } from "../../api/activity";
import type { HostEventItem } from "../../types/activity";

export function HostEventPanel(props: { gameId: number; linkedAccountId: number; turn: number }) {
    const [items, setItems] = useState<HostEventItem[]>([]);
    const [open, setOpen] = useState(true);

    useEffect(() => {
        let active = true;
        void getHostEvents(props.gameId, props.linkedAccountId, props.turn)
            .then((data) => { if (active) setItems(data.events); })
            .catch(() => { if (active) setItems([]); });
        return () => { active = false; };
    }, [props.gameId, props.linkedAccountId, props.turn]);

    if (items.length === 0) return null;
    if (!open) {
        return <button className="secondary-button" onClick={() => setOpen(true)} type="button">Host events · {items.length}</button>;
    }

    return (
        <div style={{ maxHeight: 190, overflowY: "auto", padding: 8, border: "1px solid #7b4148", borderRadius: 8, background: "rgba(18,12,16,.96)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <div><div className="eyebrow">Host events · T{props.turn}</div><strong>{items.length} system fact{items.length === 1 ? "" : "s"}</strong></div>
                <button className="secondary-button" onClick={() => setOpen(false)} style={{ padding: "3px 7px" }} type="button">Hide</button>
            </div>
            {items.map((item, index) => (
                <div key={`${item.event_type}:${index}`} style={{ marginTop: 7, color: "#ffaaaa", fontSize: 12 }}>
                    <strong>{item.summary}</strong>
                    <div style={{ color: "#91a9c8", fontSize: 10, marginTop: 2 }}>
                        factual source: {item.sources.map((source) => source.planets_username).join(", ")}
                    </div>
                </div>
            ))}
        </div>
    );
}
