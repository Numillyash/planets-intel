import { useEffect, useMemo, useState } from "react";

import { getGameActivity } from "../../api/activity";
import type { GameActivityItem } from "../../types/activity";


function activityKind(item: GameActivityItem): string {
    if (item.activity_type === 10) return "System";
    if (item.activity_type === 5) return "Diplomacy";
    return item.activity_type === null
        ? "Unclassified activity"
        : `Activity type ${item.activity_type}`;
}


function readableMessage(value: string | null): string {
    if (!value) return "(no message text)";
    return value
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]*>/g, "")
        .trim();
}


export function CommunicationsPanel(props: {
    gameId: number;
    linkedAccountId: number;
}) {
    const [items, setItems] = useState<GameActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        void getGameActivity(props.gameId, props.linkedAccountId)
            .then((response) => {
                if (!active) return;
                setItems(response.items);
            })
            .catch((reason: unknown) => {
                if (!active) return;
                setItems([]);
                setError(reason instanceof Error ? reason.message : "Failed to load communications");
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => { active = false; };
    }, [props.gameId, props.linkedAccountId]);

    const counts = useMemo(() => {
        let system = 0;
        let diplomacy = 0;
        let unclassified = 0;
        for (const item of items) {
            if (item.activity_type === 10) system += 1;
            else if (item.activity_type === 5) diplomacy += 1;
            else unclassified += 1;
        }
        return { system, diplomacy, unclassified };
    }, [items]);

    return (
        <section className="panel dashboard-embedded-panel">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">Observer communications</div>
                    <h2>Communications</h2>
                    <p>
                        Raw Planets.nu activity visible to this linked account. Unknown
                        activity/scope values stay unclassified until confirmed by a real
                        player-message sample.
                    </p>
                </div>
            </div>

            {loading && <p>Loading communications…</p>}
            {error && <p>{error}</p>}

            {!loading && !error && (
                <>
                    <p>
                        {items.length} records · {counts.system} system · {counts.diplomacy} diplomacy
                        {counts.unclassified > 0 ? ` · ${counts.unclassified} unclassified` : ""}
                    </p>

                    <div className="dashboard-report-list">
                        {items.length === 0 && (
                            <article className="dashboard-report-item">
                                <strong>No activity has been collected yet.</strong>
                                <small>Run a current private-intel refresh for this account.</small>
                            </article>
                        )}

                        {items.map((item) => (
                            <article
                                className="dashboard-report-item"
                                key={item.activity_id}
                            >
                                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                                    <strong>{activityKind(item)}</strong>
                                    <small>
                                        {item.turn !== null ? `T${item.turn}` : "turn ?"}
                                    </small>
                                </div>
                                <small>
                                    {item.source_name ?? "unknown source"}
                                    {item.target_name ? ` → ${item.target_name}` : ""}
                                </small>
                                <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>
                                    {readableMessage(item.message)}
                                </div>
                                <small>
                                    scope={item.scope ?? "?"}
                                    {item.date_added ? ` · ${item.date_added}` : ""}
                                    {item.parent_id ? ` · reply to #${item.parent_id}` : ""}
                                </small>
                            </article>
                        ))}
                    </div>
                </>
            )}
        </section>
    );
}
