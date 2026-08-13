import { useEffect, useState } from "react";

import { getShipLoadoutInference } from "../../api/threat";
import type {
    RankedLoadoutCandidate,
    ShipLoadoutInference,
} from "../../types/loadout";
import { FactRow } from "./DetailPrimitives";

function signed(value: number): string {
    return `${value >= 0 ? "+" : ""}${value.toLocaleString()}`;
}

function gradeColor(grade: RankedLoadoutCandidate["evidence_grade"]): string {
    if (grade === "strong") return "#82e6b1";
    if (grade === "moderate") return "#ffd978";
    return "#9db1ca";
}

export function LoadoutInference({
    gameId,
    linkedAccountId,
    turn,
    shipId,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    shipId: number;
}) {
    const [result, setResult] = useState<ShipLoadoutInference | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setResult(null);
        setError(null);
        void getShipLoadoutInference(gameId, linkedAccountId, turn, shipId)
            .then((response) => {
                if (!cancelled) setResult(response);
            })
            .catch((reason: unknown) => {
                if (!cancelled) {
                    setError(reason instanceof Error ? reason.message : "Analysis failed");
                }
            });
        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, shipId, turn]);

    if (error !== null) {
        return <p className="intel-no-facts" style={{ color: "#ff9999", marginTop: 8 }}>{error}</p>;
    }
    if (result === null) {
        return <p className="intel-no-facts" style={{ marginTop: 8 }}>Ranking evidence…</p>;
    }
    if (result.status !== "ok" || result.subject === undefined) {
        return <p className="intel-no-facts" style={{ marginTop: 8 }}>{result.detail ?? "Evidence is not available."}</p>;
    }

    const ledger = result.military_ledger;
    const candidates = result.ranked_candidates ?? [];

    return (
        <div style={{ marginTop: 10 }}>
            <strong style={{ fontSize: 12 }}>Evidence-ranked configurations</strong>
            <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                <FactRow label="Fuel tank" value={result.subject.fuel_capacity !== null ? `${result.subject.fuel_capacity} kt` : "—"} />
                <FactRow label="Cargo capacity" value={result.subject.cargo_capacity !== null ? `${result.subject.cargo_capacity} kt` : "—"} />
                <FactRow label="First observed" value={`T${result.subject.first_observed_turn}`} />
                {ledger !== undefined && <FactRow label="Public fleet" value={`${ledger.warships ?? "?"} warships${ledger.warship_delta !== null ? ` (${signed(ledger.warship_delta)})` : ""} · ${ledger.freighters ?? "?"} freighters${ledger.freighter_delta !== null ? ` (${signed(ledger.freighter_delta)})` : ""}`} />}
                {ledger !== undefined && <FactRow label="Visible fleet" value={`${ledger.visible_warships} warships · ${ledger.visible_noncombat_ships} non-combat`} />}
                {ledger?.candidate_build_military_delta !== null && ledger?.candidate_build_military_delta !== undefined && (
                    <FactRow label={`Score Δ at T${ledger.candidate_build_turn}`} value={`${signed(ledger.candidate_build_military_delta)} · warships ${ledger.candidate_build_warship_delta !== null ? signed(ledger.candidate_build_warship_delta) : "?"}`} />
                )}
            </dl>

            {ledger?.conditional_build_link && (
                <p className="intel-no-facts" style={{ marginTop: 7 }}>
                    Historical correlation is active for T{ledger.candidate_build_turn}: the public warship count changed by exactly +1. This is supporting evidence, not a factual identity claim.
                </p>
            )}

            <div className="intel-orbit-list" style={{ marginTop: 7 }}>
                {candidates.slice(0, 6).map((candidate, index) => (
                    <div className="intel-orbit-item" key={`${candidate.engine_id}:${candidate.beam_id}:${candidate.torpedo_id}`} style={{ cursor: "default", alignItems: "flex-start" }}>
                        <span className="intel-orbit-symbol legend-orbit" style={{ marginTop: 3 }} />
                        <span style={{ minWidth: 0 }}>
                            <strong>#{index + 1} · {candidate.beam_name ?? "?"} · {candidate.torpedo_name ?? "?"}</strong>
                            <small>{candidate.engine_name ?? "engine ?"}{candidate.build_military_score !== null ? ` · base score ${candidate.build_military_score.toLocaleString()}` : ""}{candidate.military_delta_residual !== null ? ` · residual ${signed(candidate.military_delta_residual)}` : ""}</small>
                            <small>component mass {candidate.weapon_mass ?? "?"} kt{candidate.max_fuel_if_no_cargo_or_ammo !== null ? ` · fuel ceiling ${candidate.max_fuel_if_no_cargo_or_ammo} kt` : ""}{candidate.max_fuel_fill_ratio !== null ? ` (${Math.round(candidate.max_fuel_fill_ratio * 100)}%)` : ""}</small>
                            <small style={{ color: gradeColor(candidate.evidence_grade) }}>{candidate.evidence_grade} evidence · score {candidate.evidence_points}</small>
                        </span>
                    </div>
                ))}
            </div>

            <p className="intel-no-facts" style={{ marginTop: 7 }}>
                Fuel is a soft prior, not an observed value. The ceiling assumes zero hidden cargo and zero loaded ammunition. Residual score can include ammunition, minefields, fixed defenses and unrelated fleet changes.
            </p>
            <p className="intel-no-facts" style={{ marginTop: 4 }}>
                First observation is not proof of origin; fog of war can reveal an older object for the first time.
            </p>
        </div>
    );
}
