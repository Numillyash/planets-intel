import { useEffect, useState } from "react";
import { getHostEvents } from "../../api/activity";
import type { HostEventItem } from "../../types/activity";

export function HostEventPanel(props: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    embedded?: boolean;
}) {
    const [items, setItems] = useState<HostEventItem[]>([]);
    const [open, setOpen] = useState(true);

    useEffect(() => {
        let active = true;
        void getHostEvents(props.gameId, props.linkedAccountId, props.turn)
            .then((data) => { if (active) setItems(data.events); })
            .catch(() => { if (active) setItems([]); });
        return () => { active = false; };
    }, [props.gameId, props.linkedAccountId, props.turn]);

    if (items.length === 0) {
        return props.embedded ? (
            <section className="panel dashboard-embedded-panel">
                <div className="panel-header">
                    <div>
                        <h2>Reports</h2>
                        <p>No structured host reports are available for turn {props.turn}.</p>
                    </div>
                </div>
            </section>
        ) : null;
    }

    if (!open && !props.embedded) {
        return (
            <button
                className="secondary-button"
                onClick={() => setOpen(true)}
                type="button"
            >
                Host events · {items.length}
            </button>
        );
    }

    return (
        <section className={props.embedded ? "panel dashboard-embedded-panel" : undefined}>
            <div
                style={{
                    maxHeight: props.embedded ? "none" : 190,
                    overflowY: "auto",
                    padding: props.embedded ? 0 : 8,
                    border: props.embedded ? 0 : "1px solid #7b4148",
                    borderRadius: props.embedded ? 0 : 8,
                    background: props.embedded ? "transparent" : "rgba(18,12,16,.96)",
                }}
            >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <div>
                        <div className="eyebrow">Reports · T{props.turn}</div>
                        <strong>{items.length} host fact{items.length === 1 ? "" : "s"}</strong>
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

                <div className="dashboard-report-list">
                    {items.map((item, index) => (
                        <article className="dashboard-report-item" key={`${item.event_type}:${index}`}>
                            <strong>{item.summary}</strong>
                            <small>
                                {item.event_type.replaceAll("_", " ")}
                                {item.planet_id !== null ? ` · planet #${item.planet_id}` : ""}
                                {item.x !== null && item.y !== null ? ` · ${item.x}, ${item.y}` : ""}
                            </small>
                            <small>
                                factual source: {item.sources.map((source) => source.planets_username).join(", ")}
                            </small>
                        </article>
                    ))}
                </div>
            </div>
        </section>
    );
}
