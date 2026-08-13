import { useEffect, useState } from "react";

import { getShipLoadoutInference } from "../../api/threat";
import type {
    BuildEventCandidate,
    RankedLoadoutCandidate,
    ShipLoadoutInference,
} from "../../types/loadout";
import { FactRow } from "./DetailPrimitives";

function signed(value: number | null): string {
    if (value === null) return "—";
    return `${value >= 0 ? "+" : ""}${value.toLocaleString()}`;
}

function gradeColor(grade: RankedLoadoutCandidate["evidence_grade"]): string {
    if (grade === "strong") return "#82e6b1";
    if (grade === "moderate") return "#ffd978";
    return "#9db1ca";
}

function buildEventLabel(event: BuildEventCandidate): string {
    return `T${event.turn}: ${signed(event.warship_delta)} warships · ${signed(event.military_delta)} military`;
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
    const buildEvents = ledger?.candidate_build_events ?? [];
    const engineConstraint = result.engine_constraint;

    return (
        <div style={{ marginTop: 10 }}>
            <strong style={{ fontSize: 12 }}>Evidence-ranked configurations</strong>
            <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                <FactRow label="Fuel tank" value={result.subject.fuel_capacity !== null ? `${result.subject.fuel_capacity} kt` : "—"} />
                <FactRow label="Cargo capacity" value={result.subject.cargo_capacity !== null ? `${result.subject.cargo_capacity} kt` : "—"} />
                <FactRow label="First observed" value={`T${result.subject.first_observed_turn}`} />
                <FactRow label="Observed warp" value={result.subject.observed_warp ?? "—"} />
                {engineConstraint?.kind === "hard_minimum_tech" && (
                    <FactRow label="Engine constraint" value={`Tech ${engineConstraint.min_engine_tech}+`} />
                )}
                {ledger !== undefined && <FactRow label="Public fleet" value={`${ledger.warships ?? "?"} warships${ledger.warship_delta !== null ? ` (${signed(ledger.warship_delta)})` : ""} · ${ledger.freighters ?? "?"} freighters${ledger.freighter_delta !== null ? ` (${signed(ledger.freighter_delta)})` : ""}`} />}
                {ledger !== undefined && <FactRow label="Visible fleet" value={`${ledger.visible_warships} warships · ${ledger.visible_noncombat_ships} non-combat`} />}
            </dl>

            {engineConstraint !== undefined && (
                <p className="intel-no-facts" style={{ marginTop: 7 }}>
                    {engineConstraint.detail}
                </p>
            )}

            <strong style={{ display: "block", fontSize: 11, marginTop: 10 }}>Candidate construction events</strong>
            {buildEvents.length === 0 ? (
                <p className="intel-no-facts" style={{ marginTop: 5 }}>No positive public warship-growth event is stored before the first factual sighting.</p>
            ) : (
                <div className="intel-orbit-list" style={{ marginTop: 5 }}>
                    {buildEvents.map((event) => (
                        <div className="intel-orbit-item" key={event.turn} style={{ cursor: "default", alignItems: "flex-start" }}>
                            <span className="intel-orbit-symbol legend-orbit" style={{ marginTop: 3 }} />
                            <span style={{ minWidth: 0 }}>
                                <strong>{buildEventLabel(event)}</strong>
                                <small>freighters {signed(event.freighter_delta)} · planets {signed(event.planet_delta)} · bases {signed(event.starbase_delta)} · inventory {signed(event.inventory_delta)}</small>
                            </span>
                        </div>
                    ))}
                </div>
            )}

            <div className="intel-orbit-list" style={{ marginTop: 10 }}>
                {candidates.slice(0, 8).map((candidate, index) => (
                    <div className="intel-orbit-item" key={`${candidate.engine_id}:${candidate.beam_id}:${candidate.torpedo_id}:${candidate.build_turn}`} style={{ cursor: "default", alignItems: "flex-start" }}>
                        <span className="intel-orbit-symbol legend-orbit" style={{ marginTop: 3 }} />
                        <span style={{ minWidth: 0 }}>
                            <strong>#{index + 1} · {candidate.beam_name ?? "?"} · {candidate.torpedo_name ?? "?"}</strong>
                            <small>{candidate.engine_name ?? "engine ?"}{candidate.build_military_score !== null ? ` · base score ${candidate.build_military_score.toLocaleString()}` : ""}</small>
                            {candidate.build_turn !== null && (
                                <small>T{candidate.build_turn} hypothesis · public ΔMilitary {candidate.build_military_delta !== null ? signed(candidate.build_military_delta) : "?"}{candidate.military_delta_residual !== null ? ` · residual ${signed(candidate.military_delta_residual)}` : ""}</small>
                            )}
                            <small>component mass {candidate.weapon_mass ?? "?"} kt{candidate.max_fuel_if_no_cargo_or_ammo !== null ? ` · fuel ceiling ${candidate.max_fuel_if_no_cargo_or_ammo} kt` : ""}{candidate.max_fuel_fill_ratio !== null ? ` (${Math.round(candidate.max_fuel_fill_ratio * 100)}%)` : ""}</small>
                            <small style={{ color: gradeColor(candidate.evidence_grade) }}>{candidate.evidence_grade} evidence · score {candidate.evidence_points}</small>
                        </span>
                    </div>
                ))}
            </div>

            <p className="intel-no-facts" style={{ marginTop: 7 }}>
                Every positive public warship-growth event before the first factual sighting is evaluated independently. A matching turn is inference, not proof that this exact ship was constructed then.
            </p>
            <p className="intel-no-facts" style={{ marginTop: 4 }}>
                {engineConstraint?.unlimited_fuel
                    ? "Fuel-fill ranking is disabled for this Unlimited Fuel ruleset."
                    : "Fuel is a soft prior, not an observed value. The ceiling assumes zero hidden cargo and zero loaded ammunition."}
                {" "}Military residual can include ammunition, minefields, defenses, losses and unrelated fleet changes.
            </p>
        </div>
    );
}
