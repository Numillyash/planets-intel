import { useEffect, useState, type FormEvent } from "react";

import type { PlayerInfo } from "../../types/api";
import type { PublicArchiveTurn } from "../../types/publicArchive";

interface Props {
    archive: PublicArchiveTurn | null;
    players: PlayerInfo[];
    finalTurn: number;
    loading: boolean;
    error: string | null;
    notice: string | null;
    onOpenTurn: (slot: number, turn: number) => void;
    onOpenLatest: (slot: number) => void;
}

export function PublicArchiveTimeMachine({
    archive, players, finalTurn, loading, error, notice, onOpenTurn, onOpenLatest,
}: Props) {
    const validPlayers = players.filter((p) => p.slot_id > 0 && p.slot_id <= 35 && p.race_id < 100);
    const defaultSlot = archive?.player_slot_id ?? validPlayers[0]?.slot_id ?? 1;
    const [slot, setSlot] = useState(defaultSlot);
    const [turn, setTurn] = useState(archive?.turn ?? finalTurn);

    useEffect(() => {
        if (archive === null) return;
        setSlot(archive.player_slot_id);
        setTurn(archive.turn);
    }, [archive?.game_id, archive?.player_slot_id, archive?.turn]);

    const isValid = Number.isSafeInteger(slot) && validPlayers.some((p) => p.slot_id === slot)
        && Number.isSafeInteger(turn) && turn >= 1 && turn <= finalTurn;

    function open(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (isValid && !loading) onOpenTurn(slot, turn);
    }

    function step(delta: number) {
        const next = turn + delta;
        if (loading || !isValid || next < 1 || next > finalTurn) return;
        setTurn(next);
        onOpenTurn(slot, next);
    }

    return (
        <section className="panel public-archive-time-machine">
            <div className="panel-header">
                <div>
                    <div className="eyebrow">Historical RST · read-only</div>
                    <h2>Time machine</h2>
                    <p>Choose a turn and player perspective. The selected snapshot becomes active across the Dashboard, map and object lists.</p>
                </div>
            </div>
            <form onSubmit={open} className="public-archive-time-controls">
                <label htmlFor="public-archive-slot">Perspective
                    <select id="public-archive-slot" value={slot}
                        disabled={loading}
                        onChange={(event) => setSlot(Number(event.target.value))}>
                        {validPlayers.map((p) => <option key={p.slot_id} value={p.slot_id}>
                            #{p.slot_id} · {p.username}
                        </option>)}
                    </select>
                </label>
                <label htmlFor="public-archive-turn">Turn
                    <input id="public-archive-turn" type="number" min={1} max={finalTurn}
                        value={turn} disabled={loading}
                        onChange={(event) => setTurn(Number(event.target.value))} />
                </label>
                <div className="public-archive-time-actions">
                    <button type="button" className="secondary-button" onClick={() => step(-1)}
                        disabled={loading || !isValid || turn <= 1} aria-label="Previous turn">←</button>
                    <button type="button" className="secondary-button" onClick={() => step(1)}
                        disabled={loading || !isValid || turn >= finalTurn} aria-label="Next turn">→</button>
                    <button type="submit" className="primary-button" disabled={loading || !isValid}>
                        {loading ? "Loading…" : "Open turn"}
                    </button>
                    <button type="button" className="secondary-button" disabled={loading || validPlayers.length === 0}
                        onClick={() => { setTurn(finalTurn); onOpenLatest(slot); }}>Latest</button>
                </div>
            </form>
            <div className="public-archive-time-note">
                {archive !== null
                    ? `Displayed: T${archive.turn} · slot #${archive.player_slot_id}`
                    : loading ? "Retrieving the selected historical turn…" : "No historical snapshot loaded."}
                {notice !== null && <p role="status">{notice}</p>}
                {error !== null && <p role="alert" className="public-archive-error">{error}</p>}
            </div>
        </section>
    );
}
