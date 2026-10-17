import { useEffect, useMemo, useRef, useState } from "react";

import { getGame, getScoreHistory } from "../../api/client";
import { getPublicArchiveTurn } from "../../api/publicArchive";
import type { GameDetailsResponse, ScoreHistoryResponse } from "../../types/api";
import type { PublicArchiveTurn } from "../../types/publicArchive";
import { GameDashboard } from "./GameDashboard";
import "./intelboard-game-picker.css";

export function PublicSectorExplorer({ gameId }: { gameId: number }) {
    const [sectorInput, setSectorInput] = useState(String(gameId));
    const archiveRequestRevision = useRef(0);
    const [game, setGame] = useState<GameDetailsResponse | null>(null);
    const [history, setHistory] = useState<ScoreHistoryResponse | null>(null);
    const [slot, setSlot] = useState("4");
    const [turn, setTurn] = useState("17");
    const [archive, setArchive] = useState<PublicArchiveTurn | null>(null);
    const [loading, setLoading] = useState(true);
    const [archiveLoading, setArchiveLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [archiveError, setArchiveError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        archiveRequestRevision.current += 1;
        setLoading(true);
        setError(null);
        setGame(null);
        setArchive(null);
        void Promise.all([
            getGame(gameId),
            getScoreHistory(gameId).catch(() => null),
        ]).then(([details, scoreHistory]) => {
            if (cancelled) return;
            if (details.game.is_private) {
                setError("This sector is private. Public view is unavailable.");
                return;
            }
            setGame(details);
            setHistory(scoreHistory);
            const slots = details.players
                .filter((item) => item.slot_id > 0 && item.race_id < 100)
                .map((item) => item.slot_id);
            const preferred = slots.includes(4) ? 4 : (slots[0] ?? 1);
            setSlot(String(preferred));
            setTurn(String(Math.min(17, Math.max(details.game.turn, 1))));
        }).catch((reason) => {
            if (!cancelled) setError(
                reason instanceof Error ? reason.message : "Failed to load public sector",
            );
        }).finally(() => {
            if (!cancelled) setLoading(false);
        });
        return () => { cancelled = true; };
    }, [gameId]);

    const scores = useMemo(() => {
        const result = new Map<number, ScoreHistoryResponse["items"][number]>();
        for (const item of history?.items ?? []) {
            if (item.turn === game?.game.turn) result.set(item.slot_id, item);
        }
        return result;
    }, [history, game]);

    async function loadArchive() {
        if (game?.game.status_id !== 3) return;
        const playerId = Number(slot);
        const selectedTurn = Number(turn);
        if (!Number.isSafeInteger(playerId) || !Number.isSafeInteger(selectedTurn)
            || playerId < 1 || selectedTurn < 1 || selectedTurn > game.game.turn) return;
        const revision = ++archiveRequestRevision.current;
        setArchiveLoading(true);
        setArchiveError(null);
        setArchive(null);
        try {
            const data = await getPublicArchiveTurn(gameId, playerId, selectedTurn);
            if (archiveRequestRevision.current !== revision) return;
            if (data.game_id !== gameId
                || data.turn !== selectedTurn
                || data.player_slot_id !== playerId) {
                throw new Error("Historical result identity does not match selection");
            }
            setArchive(data);
        } catch (reason) {
            if (archiveRequestRevision.current === revision) {
                setArchiveError(reason instanceof Error ? reason.message : "Archive turn unavailable");
            }
        } finally {
            if (archiveRequestRevision.current === revision) setArchiveLoading(false);
        }
    }

    return (
        <main className="intelboard-public-sector-view">
            <section className="intelboard-public-sector-entry">
                <div>
                    <div className="eyebrow">PUBLIC SECTOR · STANDARD DASHBOARD · READ ONLY</div>
                    <h1>{game?.game.name ?? `Sector #${gameId}`}</h1>
                    <p>
                        Same IntelBoard game tabs. Public facts for active games;
                        archived player-perspective RST only for verified finished sectors.
                    </p>
                    <p><a href="/intelboard">← Back to my games</a></p>
                </div>
                <form onSubmit={(event) => {
                    event.preventDefault();
                    const nextId = Number(sectorInput.trim());
                    if (Number.isSafeInteger(nextId) && nextId > 0) {
                        window.location.assign(`/intelboard/public/${nextId}`);
                    }
                }}>
                    <label htmlFor="explorer-sector-id">Game ID</label>
                    <input id="explorer-sector-id" min={1} step={1}
                        type="number" value={sectorInput} required
                        onChange={(event) => setSectorInput(event.target.value)}
                    />
                    <button type="submit" className="primary-button"
                        disabled={!Number.isSafeInteger(Number(sectorInput.trim()))
                            || Number(sectorInput.trim()) <= 0}>Analyze</button>
                </form>
            </section>

            {loading ? <section className="panel"><p>Loading public sector metadata…</p></section> : null}
            {error !== null ? <section className="panel"><p role="alert">{error}</p></section> : null}

            {game !== null && (
                <>
                    {game.game.status_id === 3 && (
                        <section className="panel">
                            <div className="panel-header">
                                <div>
                                    <div className="eyebrow">Completed sector · read-only historical loadturn</div>
                                    <h2>View historical turn</h2>
                                    <p>Choose whose perspective to inspect. No linked observer or API key is used.</p>
                                </div>
                            </div>
                            <form
                                style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "16px 22px" }}
                                onSubmit={(event) => { event.preventDefault(); void loadArchive(); }}
                            >
                                <label>Player slot
                                    <select value={slot} onChange={(event) => { archiveRequestRevision.current += 1; setSlot(event.target.value); setArchive(null); setArchiveLoading(false); }}>
                                        {game.players.filter((p) => p.slot_id > 0 && p.race_id < 100)
                                            .map((p) => (
                                                <option key={p.slot_id} value={p.slot_id}>
                                                    #{p.slot_id} · {p.username}
                                                </option>
                                            ))}
                                    </select>
                                </label>
                                <label>Turn
                                    <input type="number" min={1} max={game.game.turn}
                                        value={turn} onChange={(event) => { archiveRequestRevision.current += 1; setTurn(event.target.value); setArchive(null); setArchiveLoading(false); }} />
                                </label>
                                <button className="primary-button" type="submit"
                                    disabled={archiveLoading || !Number.isSafeInteger(Number(turn))
                                        || Number(turn) < 1 || Number(turn) > game.game.turn}>
                                    {archiveLoading ? "Loading RST…" : "Open turn"}
                                </button>
                            </form>
                            {archiveError !== null && <p style={{ padding: "0 22px 16px" }} role="alert">
                                {archiveError}
                            </p>}
                        </section>
                    )}
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
                    />
                </>
            )}
        </main>
    );
}
