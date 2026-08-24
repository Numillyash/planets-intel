import { useEffect, useMemo, useRef, useState } from "react";

import { getGameActivity, sendGameMessage } from "../../api/activity";
import { getGame, getPlanetsAccounts } from "../../api/client";
import type { PlayerInfo } from "../../types/api";
import type { GameActivityItem } from "../../types/activity";
import "./operational-shell-v2.css";
import "./operational-dashboard-bridge.css";


type ChannelKind = "general" | "private" | "activity";
type ComposeMode = "general" | "private";

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


function compareNewestFirst(left: GameActivityItem, right: GameActivityItem): number {
    const leftDate = left.date_added ?? "";
    const rightDate = right.date_added ?? "";
    if (leftDate !== rightDate) return rightDate.localeCompare(leftDate);
    return right.activity_id - left.activity_id;
}


function compareOldestFirst(left: GameActivityItem, right: GameActivityItem): number {
    const leftDate = left.date_added ?? "";
    const rightDate = right.date_added ?? "";
    if (leftDate !== rightDate) return leftDate.localeCompare(rightDate);
    return left.activity_id - right.activity_id;
}


function newestFirst(items: GameActivityItem[]): GameActivityItem[] {
    return [...items].sort(compareNewestFirst);
}


function threadedOrder(items: GameActivityItem[]): GameActivityItem[] {
    const byId = new Map(items.map((item) => [item.activity_id, item] as const));
    const childrenByParent = new Map<number, GameActivityItem[]>();
    const roots: GameActivityItem[] = [];

    for (const item of items) {
        const parentId = item.parent_id;
        if (parentId !== null && parentId > 0 && byId.has(parentId)) {
            const children = childrenByParent.get(parentId) ?? [];
            children.push(item);
            childrenByParent.set(parentId, children);
        } else {
            roots.push(item);
        }
    }

    roots.sort(compareNewestFirst);
    for (const children of childrenByParent.values()) children.sort(compareOldestFirst);

    const ordered: GameActivityItem[] = [];
    const visited = new Set<number>();
    const appendThread = (item: GameActivityItem) => {
        if (visited.has(item.activity_id)) return;
        visited.add(item.activity_id);
        ordered.push(item);
        for (const child of childrenByParent.get(item.activity_id) ?? []) {
            appendThread(child);
        }
    };

    for (const root of roots) appendThread(root);
    for (const item of newestFirst(items)) appendThread(item);
    return ordered;
}


function newestKey(items: GameActivityItem[]): string {
    let key = "";
    for (const item of items) {
        const candidate = `${item.date_added ?? ""}:${String(item.activity_id).padStart(12, "0")}`;
        if (candidate > key) key = candidate;
    }
    return key;
}


function normalizedConversationPlayerIds(item: GameActivityItem): number[] {
    return [...new Set(item.conversation_player_ids ?? [])]
        .filter((value) => Number.isInteger(value) && value > 0)
        .sort((left, right) => left - right);
}


function privateChannelKey(item: GameActivityItem): string {
    const playerIds = normalizedConversationPlayerIds(item);
    if (playerIds.length > 0) return `private:slots:${playerIds.join(",")}`;
    if (item.conversation_with_id !== null) return `private:${item.conversation_with_id}`;
    if (item.conversation_with_name) return `private:name:${item.conversation_with_name}`;
    return `private:thread:${item.thread_root_id ?? item.activity_id}`;
}


function privateChannelLabel(item: GameActivityItem): string {
    return item.conversation_with_name ?? "Private thread";
}


function chatChannelFromLocation(): string {
    return new URLSearchParams(window.location.search).get("chat") ?? "general";
}


function replaceChatChannelInLocation(channelKey: string): void {
    const url = new URL(window.location.href);
    url.searchParams.set("chat", channelKey);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}


function recipientIdsForChannel(
    channel: CommunicationChannel,
    players: PlayerInfo[],
): number[] {
    if (channel.kind !== "private") return [];

    for (const item of channel.items) {
        const ids = normalizedConversationPlayerIds(item);
        if (ids.length > 0) return ids;
    }

    const item = channel.items.find((candidate) =>
        candidate.conversation_with_id !== null
        || candidate.conversation_with_name !== null,
    );
    if (item === undefined) return [];

    if (item.conversation_with_id !== null) {
        const player = players.find(
            (candidate) => candidate.account_id === item.conversation_with_id,
        );
        return player ? [player.slot_id] : [];
    }

    const name = item.conversation_with_name?.trim().toLocaleLowerCase();
    if (!name) return [];
    const player = players.find(
        (candidate) => candidate.username.trim().toLocaleLowerCase() === name,
    );
    return player ? [player.slot_id] : [];
}


function replyPreview(item: GameActivityItem): string {
    const text = readableMessage(item.message).replace(/\s+/g, " ").trim();
    if (text.length <= 180) return text;
    return `${text.slice(0, 177)}…`;
}


export function CommunicationsDashboardPanel(props: {
    gameId: number;
    linkedAccountId: number;
}) {
    const [items, setItems] = useState<GameActivityItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshRevision, setRefreshRevision] = useState(0);
    const [selectedChannelKey, setSelectedChannelKey] = useState(
        () => chatChannelFromLocation(),
    );

    const [players, setPlayers] = useState<PlayerInfo[]>([]);
    const [senderSlotId, setSenderSlotId] = useState<number | null>(null);
    const [rosterError, setRosterError] = useState<string | null>(null);
    const [composeOpen, setComposeOpen] = useState(false);
    const [composeMode, setComposeMode] = useState<ComposeMode>("general");
    const [recipientIds, setRecipientIds] = useState<number[]>([]);
    const [replyTarget, setReplyTarget] = useState<GameActivityItem | null>(null);
    const [draftBody, setDraftBody] = useState("");
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState<string | null>(null);
    const [sendNotice, setSendNotice] = useState<string | null>(null);
    const [sendWarning, setSendWarning] = useState<string | null>(null);
    const composerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        const handlePopState = () => setSelectedChannelKey(chatChannelFromLocation());
        window.addEventListener("popstate", handlePopState);
        return () => window.removeEventListener("popstate", handlePopState);
    }, []);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        void getGameActivity(props.gameId, props.linkedAccountId)
            .then((response) => {
                if (active) setItems(response.items);
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
    }, [props.gameId, props.linkedAccountId, refreshRevision]);

    useEffect(() => {
        let active = true;
        setRosterError(null);
        void Promise.all([getGame(props.gameId), getPlanetsAccounts()])
            .then(([game, accounts]) => {
                if (!active) return;
                const linked = accounts.accounts.find(
                    (account) => account.id === props.linkedAccountId,
                ) ?? null;
                const sender = linked === null
                    ? null
                    : game.players.find(
                        (player) => linked.planets_account_id !== null
                            && player.account_id === linked.planets_account_id,
                    ) ?? game.players.find(
                        (player) => player.username.trim().toLocaleLowerCase()
                            === linked.planets_username.trim().toLocaleLowerCase(),
                    ) ?? null;
                setPlayers(game.players);
                setSenderSlotId(sender?.slot_id ?? null);
                if (linked === null || sender === null) {
                    setRosterError(
                        "Writable observer slot could not be resolved from the current game roster.",
                    );
                }
            })
            .catch((reason: unknown) => {
                if (!active) return;
                setPlayers([]);
                setSenderSlotId(null);
                setRosterError(
                    reason instanceof Error ? reason.message : "Failed to load message recipients",
                );
            });
        return () => { active = false; };
    }, [props.gameId, props.linkedAccountId]);

    const channels = useMemo<CommunicationChannel[]>(() => {
        const general = items.filter((item) => item.kind === "player_message");
        const activity = items.filter((item) =>
            item.kind === "system"
            || item.kind === "diplomacy"
            || item.kind === "unclassified",
        );
        const privateGroups = new Map<string, { label: string; items: GameActivityItem[] }>();

        for (const item of items) {
            if (item.kind !== "private_message") continue;
            const key = privateChannelKey(item);
            const existing = privateGroups.get(key);
            if (existing) existing.items.push(item);
            else privateGroups.set(key, { label: privateChannelLabel(item), items: [item] });
        }

        const privateChannels = [...privateGroups.entries()]
            .map(([key, group]): CommunicationChannel => ({
                key,
                kind: "private",
                label: group.label,
                items: threadedOrder(group.items),
                latestSortKey: newestKey(group.items),
            }))
            .sort((left, right) => right.latestSortKey.localeCompare(left.latestSortKey));

        return [
            {
                key: "general",
                kind: "general",
                label: "General",
                items: threadedOrder(general),
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

    useEffect(() => {
        if (loading) return;
        if (channels.some((channel) => channel.key === selectedChannelKey)) return;
        setSelectedChannelKey("general");
        replaceChatChannelInLocation("general");
    }, [channels, loading, selectedChannelKey]);

    const selectedChannel = channels.find(
        (channel) => channel.key === selectedChannelKey,
    ) ?? channels[0];
    const privateChannels = channels.filter((channel) => channel.kind === "private");
    const generalChannel = channels.find((channel) => channel.kind === "general");
    const activityChannel = channels.find((channel) => channel.kind === "activity");
    const recipientPlayers = players
        .filter((player) =>
            player.status === 1
            && player.race_id < 100
            && player.slot_id !== senderSlotId,
        )
        .sort((left, right) => left.slot_id - right.slot_id);

    function selectChannel(channelKey: string) {
        setSelectedChannelKey(channelKey);
        replaceChatChannelInLocation(channelKey);
    }

    function scrollComposerIntoView() {
        window.requestAnimationFrame(() => {
            composerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    }

    function openNewMessage() {
        setReplyTarget(null);
        setComposeMode("general");
        setRecipientIds([]);
        setSendError(null);
        setSendNotice(null);
        setSendWarning(null);
        setComposeOpen(true);
        scrollComposerIntoView();
    }

    function replyToMessage(item: GameActivityItem, channel: CommunicationChannel) {
        setReplyTarget(item);
        setSendError(null);
        setSendNotice(null);
        setSendWarning(null);
        if (channel.kind === "private") {
            const channelRecipients = recipientIdsForChannel(channel, recipientPlayers)
                .filter((slotId) => recipientPlayers.some((player) => player.slot_id === slotId));
            setComposeMode("private");
            setRecipientIds(channelRecipients);
        } else {
            setComposeMode("general");
            setRecipientIds([]);
        }
        setComposeOpen(true);
        scrollComposerIntoView();
    }

    function chooseComposeMode(mode: ComposeMode) {
        setComposeMode(mode);
        setReplyTarget(null);
        setSendError(null);
        if (mode === "general") setRecipientIds([]);
    }

    function toggleRecipient(slotId: number) {
        setReplyTarget(null);
        setRecipientIds((current) =>
            current.includes(slotId)
                ? current.filter((item) => item !== slotId)
                : [...current, slotId].sort((left, right) => left - right),
        );
    }

    async function handleSend() {
        const body = draftBody.trim();
        if (!body || sending) return;
        if (composeMode === "private" && recipientIds.length === 0) return;

        const recipients = composeMode === "general" ? [] : recipientIds;
        const names = recipientPlayers
            .filter((player) => recipients.includes(player.slot_id))
            .map((player) => `${player.username} (slot ${player.slot_id})`);
        const destination = composeMode === "general" ? "the Public Board" : names.join(", ");
        const replyNote = replyTarget === null
            ? ""
            : `\n\nReply target in IntelBoard: #${replyTarget.activity_id} from ${replyTarget.source_name ?? "unknown sender"}.`;
        const confirmed = window.confirm(
            `Send this ${composeMode === "general" ? "public" : "private"} message via Planets.nu to ${destination}?${replyNote}`,
        );
        if (!confirmed) return;

        setSending(true);
        setSendError(null);
        setSendNotice(null);
        setSendWarning(null);
        try {
            const result = await sendGameMessage(
                props.gameId,
                props.linkedAccountId,
                recipients,
                body,
            );
            if (result.upstream_accepted && result.reconciled) {
                setSendNotice(
                    composeMode === "general"
                        ? "Public Board message sent and observed in the refreshed Planets.nu communications feed."
                        : "Private message sent and observed in the refreshed Planets.nu communications feed.",
                );
            } else if (result.upstream_accepted) {
                setSendWarning(
                    result.reconciliation_detail
                    ?? "Planets.nu accepted the message, but the refreshed feed has not confirmed it yet.",
                );
            }
            setDraftBody("");
            setRecipientIds([]);
            setReplyTarget(null);
            setComposeOpen(false);
            setRefreshRevision((value) => value + 1);
        } catch (reason) {
            setSendError(reason instanceof Error ? reason.message : "Message send failed");
        } finally {
            setSending(false);
        }
    }

    const sendDisabled = sending
        || !draftBody.trim()
        || (composeMode === "private" && recipientIds.length === 0);
    const sendLabel = sending
        ? "Sending…"
        : composeMode === "general"
            ? "Post to Public Board"
            : `Send privately to ${recipientIds.length}`;

    return (
        <section className="panel dashboard-embedded-panel">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">Observer communications</div>
                    <h2>Communications</h2>
                    <p>
                        Public Board and direct conversations are separated. Reply actions are
                        attached to individual factual messages rather than whole conversations.
                    </p>
                </div>
                <button
                    className="primary-button"
                    onClick={() => {
                        if (composeOpen) {
                            setComposeOpen(false);
                            setReplyTarget(null);
                        } else {
                            openNewMessage();
                        }
                    }}
                    type="button"
                >
                    {composeOpen ? "Cancel" : "New message"}
                </button>
            </div>

            {sendNotice && <div className="success-card">{sendNotice}</div>}
            {sendWarning && <div className="loading-card">{sendWarning}</div>}
            {sendError && <div className="error-card">{sendError}</div>}

            {composeOpen && (
                <div
                    className="panel"
                    ref={composerRef}
                    style={{ marginTop: 12, padding: 16 }}
                >
                    <div className="eyebrow">Explicit Planets.nu write</div>
                    <h3 style={{ margin: "6px 0" }}>
                        {replyTarget === null ? "Compose message" : "Reply to message"}
                    </h3>

                    {replyTarget !== null && (
                        <div
                            style={{
                                margin: "10px 0 14px",
                                padding: "10px 12px",
                                border: "1px solid #334a65",
                                borderRadius: 8,
                                background: "#0a1521",
                            }}
                        >
                            <div style={{ color: "#91b4d7", fontSize: 11, fontWeight: 700 }}>
                                Replying to {replyTarget.source_name ?? "unknown sender"}
                                {replyTarget.turn !== null ? ` · T${replyTarget.turn}` : ""}
                                {` · message #${replyTarget.activity_id}`}
                            </div>
                            <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
                                {replyPreview(replyTarget)}
                            </div>
                            <div style={{ color: "#738aa3", fontSize: 10, marginTop: 7 }}>
                                Recipient routing is exact. The upstream Planets.nu reply-parent
                                request field is not yet verified, so no parent id is fabricated.
                            </div>
                        </div>
                    )}

                    <div className="communications-compose-mode">
                        <button
                            className={composeMode === "general" ? "is-active" : ""}
                            onClick={() => chooseComposeMode("general")}
                            type="button"
                        >
                            <strong>Public Board</strong>
                            <span>Visible to the game</span>
                        </button>
                        <button
                            className={composeMode === "private" ? "is-active" : ""}
                            onClick={() => chooseComposeMode("private")}
                            type="button"
                        >
                            <strong>Private message</strong>
                            <span>One or more player slots</span>
                        </button>
                    </div>

                    {composeMode === "private" && (
                        <div style={{ marginTop: 14 }}>
                            <div className="eyebrow">Recipients</div>
                            <div
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                                    gap: 8,
                                    marginTop: 8,
                                }}
                            >
                                {recipientPlayers.map((player) => (
                                    <label
                                        key={player.slot_id}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: 8,
                                            padding: "9px 10px",
                                            border: "1px solid #2a3d53",
                                            borderRadius: 8,
                                            background: "#0b1520",
                                        }}
                                    >
                                        <input
                                            checked={recipientIds.includes(player.slot_id)}
                                            disabled={sending}
                                            onChange={() => toggleRecipient(player.slot_id)}
                                            type="checkbox"
                                        />
                                        <span>
                                            <strong>{player.username}</strong>
                                            <small style={{ display: "block" }}>slot {player.slot_id}</small>
                                        </span>
                                    </label>
                                ))}
                            </div>
                            {rosterError && <small style={{ color: "#e69a9a" }}>{rosterError}</small>}
                        </div>
                    )}

                    <label style={{ display: "block", marginTop: 14 }}>
                        <span className="eyebrow">Message</span>
                        <textarea
                            className="communications-message-textarea"
                            disabled={sending}
                            maxLength={20000}
                            onChange={(event) => setDraftBody(event.target.value)}
                            placeholder={
                                composeMode === "general"
                                    ? "Write a Public Board message…"
                                    : "Write a private Planets.nu message…"
                            }
                            rows={6}
                            value={draftBody}
                        />
                    </label>

                    <div
                        style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: 12,
                            marginTop: 10,
                        }}
                    >
                        <small>{draftBody.length.toLocaleString()} / 20,000</small>
                        <button
                            className="primary-button"
                            disabled={sendDisabled}
                            onClick={() => void handleSend()}
                            type="button"
                        >
                            {sendLabel}
                        </button>
                    </div>
                </div>
            )}

            {loading && <div className="loading-card">Loading communications…</div>}
            {error && <div className="error-card">{error}</div>}

            {!loading && !error && (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "220px minmax(0, 1fr)",
                        gap: 14,
                        marginTop: 14,
                    }}
                >
                    <aside className="panel" style={{ padding: 10 }}>
                        <div className="eyebrow">Chat</div>
                        {generalChannel && (
                            <button
                                className="secondary-button"
                                onClick={() => selectChannel(generalChannel.key)}
                                style={{ width: "100%", marginTop: 8 }}
                                type="button"
                            >
                                General · {generalChannel.items.length}
                            </button>
                        )}

                        <div className="eyebrow" style={{ marginTop: 16 }}>Direct messages</div>
                        {privateChannels.length === 0 ? (
                            <small>No direct conversations collected.</small>
                        ) : privateChannels.map((channel) => (
                            <button
                                className="secondary-button"
                                key={channel.key}
                                onClick={() => selectChannel(channel.key)}
                                style={{ width: "100%", marginTop: 7, textAlign: "left" }}
                                type="button"
                            >
                                {channel.label} · {channel.items.length}
                            </button>
                        ))}

                        {activityChannel && (
                            <>
                                <div className="eyebrow" style={{ marginTop: 16 }}>Other</div>
                                <button
                                    className="secondary-button"
                                    onClick={() => selectChannel(activityChannel.key)}
                                    style={{ width: "100%", marginTop: 7 }}
                                    type="button"
                                >
                                    Activity · {activityChannel.items.length}
                                </button>
                            </>
                        )}
                    </aside>

                    <section className="panel" style={{ padding: 12, minWidth: 0 }}>
                        <div className="panel-header">
                            <div>
                                <div className="eyebrow">
                                    {selectedChannel?.kind === "private"
                                        ? "Direct conversation"
                                        : selectedChannel?.kind === "activity"
                                            ? "System feed"
                                            : "Public Board"}
                                </div>
                                <h3 style={{ margin: "3px 0 0" }}>{selectedChannel?.label ?? "General"}</h3>
                            </div>
                            <span>{selectedChannel?.items.length ?? 0} messages</span>
                        </div>

                        {(selectedChannel?.items.length ?? 0) === 0 ? (
                            <div className="loading-card">No messages in this channel.</div>
                        ) : (
                            <div style={{ display: "grid", gap: 8 }}>
                                {threadedOrder(selectedChannel.items).map((item) => (
                                    <article
                                        className={`communications-message-card${item.parent_id ? " is-reply" : ""}`}
                                        key={item.activity_id}
                                        style={{ position: "relative" }}
                                    >
                                        <header>
                                            <strong>{item.source_name ?? "unknown sender"}</strong>
                                            <small>{item.turn !== null ? `T${item.turn}` : ""}</small>
                                        </header>
                                        {selectedChannel.kind === "activity" && (
                                            <small>{item.kind} · type {item.activity_type ?? "?"}</small>
                                        )}
                                        <div style={{ whiteSpace: "pre-wrap", marginTop: 7 }}>
                                            {readableMessage(item.message)}
                                        </div>
                                        <footer
                                            style={{
                                                display: "flex",
                                                alignItems: "center",
                                                justifyContent: "space-between",
                                                gap: 12,
                                                marginTop: 8,
                                            }}
                                        >
                                            <small>{item.date_added ?? "date unknown"}</small>
                                            {selectedChannel.kind !== "activity" && (
                                                <button
                                                    className="secondary-button"
                                                    onClick={() => replyToMessage(item, selectedChannel)}
                                                    style={{ padding: "4px 9px", minHeight: 0 }}
                                                    type="button"
                                                >
                                                    Reply
                                                </button>
                                            )}
                                        </footer>
                                    </article>
                                ))}
                            </div>
                        )}
                    </section>
                </div>
            )}
        </section>
    );
}
