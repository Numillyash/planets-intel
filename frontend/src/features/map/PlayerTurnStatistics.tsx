import { useEffect, useMemo, useState } from "react";

import { getScoreHistory } from "../../api/client";
import type { ScoreHistoryItem } from "../../types/api";
import { DetailSection } from "./DetailPrimitives";

function signed(value: number | null): string {
    if (value === null) return "—";
    return `${value > 0 ? "+" : ""}${value.toLocaleString()}`;
}

export function PlayerTurnStatistics({ gameId, slotId, toTurn, label }: {
    gameId: number;
    slotId: number;
    toTurn: number;
    label: string;
}) {
    const [rows, setRows] = useState<ScoreHistoryItem[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        async function load() {
            try {
                const history = await getScoreHistory(gameId);
                if (cancelled) return;
                setRows((history?.items ?? []).filter(
                    (item) => item.slot_id === slotId && item.turn <= toTurn,
                ));
            } catch (reason) {
                if (cancelled) return;
                setRows([]);
                setError(reason instanceof Error ? reason.message : "Turn statistics failed");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        void load();
        return () => { cancelled = true; };
    }, [gameId, slotId, toTurn]);

    const buildTurns = useMemo(
        () => rows.filter((item) => (item.delta_capital_ships ?? 0) > 0),
        [rows],
    );

    return (
        <DetailSection title={`Turn statistics · ${label}`} open={false}>
            {loading && <p className="intel-no-facts">Loading public score history…</p>}
            {error !== null && <p className="intel-no-facts" style={{ color: "#ff9999" }}>{error}</p>}
            {!loading && error === null && rows.length === 0 && (
                <p className="intel-no-facts">No stored score history for this player.</p>
            )}
            {!loading && rows.length > 0 && (
                <>
                    <p className="intel-no-facts" style={{ marginBottom: 7 }}>
                        Public turn-by-turn score history. Positive ΔW is a net warship-count increase, not proof that a particular observed ship was built on that turn.
                    </p>
                    <p className="intel-no-facts" style={{ marginBottom: 7 }}>
                        Fleet-growth turns: {buildTurns.length > 0
                            ? buildTurns.map((item) => `T${item.turn}: ${signed(item.delta_capital_ships)} warships, ${signed(item.delta_military_score)} military`).join(" · ")
                            : "none in stored history"}
                    </p>
                    <div style={{ overflowX: "auto", maxWidth: "100%" }}>
                        <table style={{ borderCollapse: "collapse", minWidth: 780, width: "100%", fontSize: 10 }}>
                            <thead>
                                <tr style={{ color: "#8fa7c5", textAlign: "right" }}>
                                    <th style={{ textAlign: "left", padding: "4px" }}>T</th>
                                    <th>War</th><th>ΔW</th><th>Fr</th><th>ΔF</th>
                                    <th>Pl</th><th>ΔP</th><th>Base</th><th>ΔB</th>
                                    <th>Military</th><th>ΔMil</th><th>Inventory</th><th>ΔInv</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((item) => {
                                    const fleetGrowth = (item.delta_capital_ships ?? 0) > 0;
                                    return (
                                        <tr key={item.turn} style={{ borderTop: "1px solid #233044", background: fleetGrowth ? "rgba(126, 211, 164, 0.07)" : undefined, textAlign: "right" }}>
                                            <td style={{ textAlign: "left", padding: "4px", fontWeight: fleetGrowth ? 700 : 400 }}>T{item.turn}</td>
                                            <td>{item.capital_ships}</td><td>{signed(item.delta_capital_ships)}</td>
                                            <td>{item.freighters}</td><td>{signed(item.delta_freighters)}</td>
                                            <td>{item.planets}</td><td>{signed(item.delta_planets)}</td>
                                            <td>{item.starbases}</td><td>{signed(item.delta_starbases)}</td>
                                            <td>{item.military_score.toLocaleString()}</td><td>{signed(item.delta_military_score)}</td>
                                            <td>{item.inventory_score.toLocaleString()}</td><td>{signed(item.delta_inventory_score)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </DetailSection>
    );
}
