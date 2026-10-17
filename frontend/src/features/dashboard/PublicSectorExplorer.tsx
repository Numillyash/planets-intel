import { useEffect, useMemo, useRef, useState } from "react";

import { getGame, getScoreHistory } from "../../api/client";
import { getPublicArchiveTurn } from "../../api/publicArchive";
import type { CurrentUserResponse, GameDetailsResponse, ScoreHistoryResponse } from "../../types/api";
import type { PublicArchiveTurn } from "../../types/publicArchive";
import { GameDashboard } from "./GameDashboard";
import { GamePageHeader } from "./GamePageHeader";
import "./intelboard-game-picker.css";

/**
 * Public sector entry is a data-source controller, not a second dashboard.
 * Every RST is explicitly read-only and never mapped onto a linked observer.
 */
export function PublicSectorExplorer({
    gameId, user, onLogout,
}: {
    gameId: number;
    user: CurrentUserResponse;
    onLogout: () => Promise<void>;
}) {
    const [gameInput, setGameInput] = useState(String(gameId));
    const [loggingOut, setLoggingOut] = useState(false);
    const requestRevision = useRef(0);
    const [game, setGame] = useState<GameDetailsResponse | null>(null);
    const [history, setHistory] = useState<ScoreHistoryResponse | null>(null);
    const [archive, setArchive] = useState<PublicArchiveTurn | null>(null);
    const [gameLoading, setGameLoading] = useState(true);
    const [archiveLoading, setArchiveLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [archiveError, setArchiveError] = useState<string | null>(null);
    const [archiveNotice, setArchiveNotice] = useState<string | null>(null);

    async function openTurn(
        details: GameDetailsResponse,
        slot: number,
        selectedTurn: number,
        tryPrevious: boolean,
    ): Promise<void> {
        if (details.game.is_private || details.game.status_id !== 3) return;
        if (!Number.isSafeInteger(slot) || !Number.isSafeInteger(selectedTurn)
            || slot < 1 || slot > 35 || selectedTurn < 1
            || selectedTurn > details.game.turn
            || !details.players.some((player) => player.slot_id === slot)) return;

        const revision = ++requestRevision.current;
        setArchive(null);
        setArchiveLoading(true);
        setArchiveError(null);
        setArchiveNotice(null);

        // Last host turn may not have an RST for a given perspective. Bounded
        // fallback is explicitly disclosed; normal historical selection never
        // silently substitutes a different turn.
        const candidates = tryPrevious
            ? Array.from({ length: Math.min(3, selectedTurn) },
                (_, index) => selectedTurn - index)
            : [selectedTurn];
        let lastError: string | null = null;

        try {
            for (const candidate of candidates) {
                if (requestRevision.current !== revision) return;
                try {
                    const result = await getPublicArchiveTurn(details.game.id, slot, candidate);
                    if (requestRevision.current !== revision) return;
                    if (result.game_id !== details.game.id
                        || result.turn !== candidate || result.player_slot_id !== slot) {
                        setArchiveError("Returned historical RST identity does not match the requested game, slot and turn.");
                        return; // A source-identity failure is never retried as a missing turn.
                    }
                    setArchive(result);
                    try {
                        window.localStorage.setItem(`intelboard-public-slot:${details.game.id}`, String(slot));
                    } catch {
                        // Storage is optional. Source identity is still server-verified.
                    }
                    // Deep links and reloads must preserve the verified perspective,
                    // never the requested-but-unavailable fallback candidate.
                    const url = new URL(window.location.href);
                    url.searchParams.set("slot", String(slot));
                    url.searchParams.set("turn", String(candidate));
                    window.history.replaceState(
                        null, "", `${url.pathname}${url.search}${url.hash}`,
                    );
                    if (candidate !== selectedTurn) {
                        setArchiveNotice(
                            `Final turn T${selectedTurn} was not available for slot #${slot}. Showing verified T${candidate} instead.`,
                        );
                    }
                    return;
                } catch (reason) {
                    if (requestRevision.current !== revision) return;
                    lastError = reason instanceof Error ? reason.message : "RST unavailable";
                }
            }
            setArchiveError(
                tryPrevious
                    ? `Could not load a final archived RST for slot #${slot} (T${candidates.join(", T")}). ${lastError ?? ""}`
                    : `T${selectedTurn}, slot #${slot}: ${lastError ?? "RST unavailable"}`,
            );
        } finally {
            if (requestRevision.current === revision) setArchiveLoading(false);
        }
    }

    useEffect(() => {
        let cancelled = false;
        const revision = ++requestRevision.current;
        setGameLoading(true);
        setGame(null);
        setHistory(null);
        setArchive(null);
        setArchiveError(null);
        setArchiveNotice(null);
        setError(null);

        void (async () => {
            try {
                const details = await getGame(gameId);
                if (cancelled || requestRevision.current !== revision) return;
                if (details.game.is_private) {
                    setError("This sector is private. Public view is unavailable.");
                    return;
                }
                setGame(details);
                // Scores are cached separately. Failure to find them must not
                // block the canonical game roster or the public archived RST.
                void getScoreHistory(gameId)
                    .then((scores) => { if (!cancelled) setHistory(scores); })
                    .catch(() => { if (!cancelled) setHistory(null); });

                if (details.game.status_id === 3) {
                    const candidateSlots = details.players
                        .filter((player) => player.slot_id > 0 && player.slot_id <= 35
                            && player.race_id < 100)
                        .sort((a, b) => (a.status === 1 ? 0 : 1) -
                            (b.status === 1 ? 0 : 1) || a.slot_id - b.slot_id);
                    const query = new URLSearchParams(window.location.search);
                    const requestedSlot = Number(query.get("slot"));
                    const requestedTurn = Number(query.get("turn"));
                    const hasValidSlot = query.has("slot") && Number.isSafeInteger(requestedSlot)
                        && candidateSlots.some((player) => player.slot_id === requestedSlot);
                    const hasValidTurn = query.has("turn") && Number.isSafeInteger(requestedTurn)
                        && requestedTurn > 0 && requestedTurn <= details.game.turn;
                    let rememberedSlot: number | null = null;
                    try {
                        const saved = window.localStorage.getItem(`intelboard-public-slot:${gameId}`);
                        if (saved !== null) rememberedSlot = Number(saved);
                    } catch {
                        // Private browsing may disable storage.
                    }
                    const rememberedEligible = rememberedSlot !== null && candidateSlots.some(
                        (player) => player.slot_id === rememberedSlot,
                    );
                    const slot = hasValidSlot ? requestedSlot
                        : rememberedEligible ? rememberedSlot! : candidateSlots[0]?.slot_id;
                    const turn = hasValidTurn ? requestedTurn : details.game.turn;
                    if (slot !== undefined) {
                        await openTurn(details, slot, turn, !hasValidTurn);
                    } else {
                        setArchiveError("No eligible player slots are present in the public roster.");
                    }
                }
            } catch (reason) {
                if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load public sector");
            } finally {
                if (!cancelled) setGameLoading(false);
            }
        })();
        return () => {
            cancelled = true;
            requestRevision.current += 1;
        };
    }, [gameId]);

    const scores = useMemo(() => {
        const rows = new Map<number, ScoreHistoryResponse["items"][number]>();
        const selected = archive?.turn ?? game?.game.turn;
        for (const row of history?.items ?? []) {
            if (row.turn === selected) rows.set(row.slot_id, row);
        }
        return rows;
    }, [history, game, archive]);

    function openSelected(slot: number, turn: number): void {
        if (game !== null) void openTurn(game, slot, turn, false);
    }

    function openLatest(slot: number): void {
        if (game !== null) void openTurn(game, slot, game.game.turn, true);
    }

    return (
        <main className="app-shell public-archive-operational-shell">
            <GamePageHeader
                title={game?.game.name ?? `Sector #${gameId}`}
                subtitle={game?.game.short_description
                    ?? "Public completed-game archive · observer-independent, read-only"}
                status={game?.game.status_name ?? null}
                turn={game?.game.turn ?? null}
                slots={game?.game.slots ?? null}
                user={user}
                loggingOut={loggingOut}
                onLogout={() => {
                    setLoggingOut(true);
                    void onLogout().finally(() => setLoggingOut(false));
                }}
                extra={<a className="public-archive-back-link" href="/intelboard">← My games</a>}
            />
            <section className="summary-grid public-archive-scope">
                <div className="summary-card">
                    <span>Observation source</span>
                    <strong>Public archival RST</strong>
                    <small>Read-only · not a linked observer</small>
                </div>
                <div className="summary-card">
                    <span>Perspective</span>
                    <strong>{archive !== null
                        ? `Slot #${archive.player_slot_id} · T${archive.turn}`
                        : game !== null && game.game.status_id !== 3
                            ? "Public metadata" : "Loading archive"}</strong>
                    <small>Change in Time machine</small>
                </div>
                <details className="summary-card public-archive-game-switch">
                    <summary>Open another sector</summary>
                    <form onSubmit={(event) => {
                        event.preventDefault();
                        const id = Number(gameInput);
                        if (Number.isSafeInteger(id) && id > 0) {
                            window.location.assign(`/intelboard/public/${id}`);
                        }
                    }}>
                        <label htmlFor="public-archive-game-id">Game ID</label>
                        <input id="public-archive-game-id" type="number" min="1"
                            value={gameInput} onChange={(event) => setGameInput(event.target.value)}/>
                        <button type="submit" className="primary-button">Open</button>
                    </form>
                </details>
            </section>

            {gameLoading && game === null && <section className="panel public-archive-state">Loading public sector…</section>}
            {error !== null && <section className="panel public-archive-state" role="alert">{error}</section>}
            {game !== null && (
                <GameDashboard
                    game={game}
                    history={history}
                    latestScores={scores}
                    privateIntel={null}
                    selectedAccount={null}
                    refreshing={false}
                    onRefresh={() => {}}
                    publicMode
                    publicArchive={archive}
                    publicArchiveLoading={archiveLoading}
                    publicArchiveError={archiveError}
                    publicArchiveNotice={archiveNotice}
                    onOpenPublicTurn={openSelected}
                    onOpenPublicLatest={openLatest}
                />
            )}
        </main>
    );
}
