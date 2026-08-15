import { useEffect, useMemo, useState } from "react";

import { getGameActivity } from "../../api/activity";
import type { GameActivityItem } from "../../types/activity";


type ChannelKind = "general" | "private" | "activity";

interface CommunicationChannel {
    key: string;
    kind: ChannelKind;
    label: string;
    items: GameActivityItem[];
    latestSortKey: string;
}


function readableMessage(value: string | null): string {
    if (!value) return "(no message text)";
    return value
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]*>/g, "")
        .trim();
}


function newestFirst(items: GameActivityItem[]): GameActivityItem[] {
    return [...items].sort((left, right) => {
        const leftDate = left.date_added ?? "";
        const rightDate = right.date_added ?? "";
        if (leftDate !== rightDate) return rightDate.localeCompare(leftDate);
        return right.activity_id - left.activity_id;
    });
}


function newestKey(items: GameActivityItem[]): string {
    let key = "";
    for (const item of items) {
        const candidate = `${item.date_added ?? ""}:${String(item.activity_id).padStart(12, "0")}`;
        if (candidate > key) key = candidate;
    }
    return key;
}


function privateChannelKey(item: GameActivityItem): string {
    if (item.conversation_with_id !== null) {
        return `private:${item.conversation_with_id}`;
    }
    if (item.conversation_with_name) {
        return `private:name:${item.conversation_with_name}`;
    }
    return `private:thread:${item.thread_root_id ?? item.activity_id}`;
}


function privateChannelLabel(item: GameActivityItem): string {
    return item.conversation_with_name ?? "Unknown player";
}


function activityLabel(item: GameActivityItem): string {
    if (item.kind === "system") return "System";
    if (item.kind === "diplomacy") return "Diplomacy";
    return item.activity_type === null
        ? "Unclassified activity"
        : `Activity type ${item.activity_type}`;
}


export function CommunicationsPanel(props: {
    gameId: number;
    linkedAccountId: number;
}) {
    const [items, setItems] = useState<GameActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedChannelKey, setSelectedChannelKey] = useState("general");

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

    const channels = useMemo<CommunicationChannel[]>(() => {
        const general = items.filter((item) => item.kind === "player_message");
        const activity = items.filter(
            (item) => item.kind === "system" || item.kind === "diplomacy" || item.kind === "unclassified",
        );
        const privateGroups = new Map<string, { label: string; items: GameActivityItem[] }>();

        for (const item of items) {
            if (item.kind !== "private_message") continue;
            const key = privateChannelKey(item);
            const existing = privateGroups.get(key);
            if (existing) {
                existing.items.push(item);
            } else {
                privateGroups.set(key, {
                    label: privateChannelLabel(item),
                    items: [item],
                });
            }
        }

        const privateChannels: CommunicationChannel[] = [...privateGroups.entries()]
            .map(([key, group]) => ({
                key,
                kind: "private" as const,
                label: group.label,
                items: newestFirst(group.items),
                latestSortKey: newestKey(group.items),
            }))
            .sort((left, right) => right.latestSortKey.localeCompare(left.latestSortKey));

        return [
            {
                key: "general",
                kind: "general",
                label: "General",
                items: newestFirst(general),
                latestSortKey: newestKey(general),
            },
            ...privateChannels,
            {
                key: "activity",
                kind: "activity",
                label: "Activity",
                items: newestFirst(activity),
                latestSortKey: newestKey(activity),
            },
        ];
    }, [items]);

    const selectedChannel = channels.find((channel) => channel.key === selectedChannelKey) ?? channels[0];
    const privateChannels = channels.filter((channel) => channel.kind === "private");
    const generalChannel = channels.find((channel) => channel.kind === "general");
    const activityChannel = channels.find((channel) => channel.kind === "activity");

    return (
        <section className="panel dashboard-embedded-panel">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">Observer communications</div>
                    <h2>Communications</h2>
                    <p>
                        General chat and direct conversations are separated by player.
                        System and diplomacy records stay in Activity instead of mixing
                        with chat messages.
                    </p>
                </div>
            </div>

            {loading && <p>Loading communications…</p>}
            {error && <p>{error}</p>}

            {!loading && !error && (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(220px, 280px) minmax(0, 1fr)",
                        gap: 16,
                        minHeight: 430,
                    }}
                >
                    <aside
                        style={{
                            border: "1px solid rgba(104, 127, 151, 0.28)",
                            borderRadius: 10,
                            padding: 10,
                            background: "rgba(7, 13, 21, 0.45)",
                        }}
                    >
                        <div className="eyebrow" style={{ margin: "4px 6px 8px" }}>Chat</div>
                        <button
                            className={selectedChannelKey === "general" ? "secondary-button is-active" : "secondary-button"}
                            onClick={() => setSelectedChannelKey("general")}
                            style={{ width: "100%", display: "flex", justifyContent: "space-between", marginBottom: 8 }}
                            type="button"
                        >
                            <span>General</span>
                            <span>{generalChannel?.items.length ?? 0}</span>
                        </button>

                        <div className="eyebrow" style={{ margin: "14px 6px 8px" }}>Direct messages</div>
                        {privateChannels.length === 0 && (
                            <small style={{ display: "block", padding: "4px 6px 10px" }}>
                                No direct conversations collected.
                            </small>
                        )}
                        {privateChannels.map((channel) => (
                            <button
                                className={selectedChannelKey === channel.key ? "secondary-button is-active" : "secondary-button"}
                                key={channel.key}
                                onClick={() => setSelectedChannelKey(channel.key)}
                                style={{
                                    width: "100%",
                                    display: "flex",
                                    justifyContent: "space-between",
                                    gap: 8,
                                    marginBottom: 6,
                                    textAlign: "left",
                                }}
                                type="button"
                            >
                                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{channel.label}</span>
                                <span>{channel.items.length}</span>
                            </button>
                        ))}

                        <div className="eyebrow" style={{ margin: "14px 6px 8px" }}>Other</div>
                        <button
                            className={selectedChannelKey === "activity" ? "secondary-button is-active" : "secondary-button"}
                            onClick={() => setSelectedChannelKey("activity")}
                            style={{ width: "100%", display: "flex", justifyContent: "space-between" }}
                            type="button"
                        >
                            <span>Activity</span>
                            <span>{activityChannel?.items.length ?? 0}</span>
                        </button>
                    </aside>

                    <div
                        style={{
                            border: "1px solid rgba(104, 127, 151, 0.28)",
                            borderRadius: 10,
                            padding: 14,
                            minWidth: 0,
                        }}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
                            <div>
                                <div className="eyebrow">
                                    {selectedChannel?.kind === "private"
                                        ? "Direct conversation"
                                        : selectedChannel?.kind === "activity"
                                            ? "System feed"
                                            : "Player chat"}
                                </div>
                                <h3 style={{ margin: "3px 0 0" }}>{selectedChannel?.label ?? "General"}</h3>
                            </div>
                            <small>{selectedChannel?.items.length ?? 0} messages</small>
                        </div>

                        {selectedChannel?.kind === "general" && (
                            <small style={{ display: "block", marginBottom: 10 }}>
                                Player-authored messages that are not identified as direct threads.
                            </small>
                        )}

                        <div className="dashboard-report-list">
                            {(selectedChannel?.items.length ?? 0) === 0 && (
                                <article className="dashboard-report-item">
                                    <strong>No messages in this channel.</strong>
                                </article>
                            )}

                            {selectedChannel?.items.map((item) => (
                                <article
                                    className="dashboard-report-item"
                                    key={item.activity_id}
                                    style={item.parent_id ? {
                                        marginLeft: 24,
                                        borderLeftWidth: 3,
                                    } : undefined}
                                >
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                                        <strong>
                                            {selectedChannel.kind === "activity"
                                                ? activityLabel(item)
                                                : item.source_name ?? "unknown sender"}
                                        </strong>
                                        <small>{item.turn !== null ? `T${item.turn}` : "turn ?"}</small>
                                    </div>
                                    {selectedChannel.kind === "activity" && (
                                        <small>
                                            {item.source_name ?? "unknown source"}
                                            {item.target_name ? ` → ${item.target_name}` : ""}
                                        </small>
                                    )}
                                    <div style={{ whiteSpace: "pre-wrap", marginTop: 7 }}>
                                        {readableMessage(item.message)}
                                    </div>
                                    <small>
                                        {item.date_added ?? "time unknown"}
                                        {item.parent_id ? ` · reply #${item.parent_id}` : ""}
                                    </small>
                                </article>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}
