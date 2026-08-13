import { useEffect, useMemo, useState } from "react";

import { getShipThreatAnalysis } from "../../api/threat";
import type {
    ShipThreatAnalysis,
    ThreatBeamCandidate,
    ThreatRisk,
    ThreatTorpedoCandidate,
} from "../../types/threat";
import { DetailSection, FactRow } from "./DetailPrimitives";


function riskColor(risk: ThreatRisk): string {
    switch (risk) {
        case "critical": return "#ff7c8d";
        case "high": return "#ffbd70";
        case "medium": return "#ffd978";
        case "low": return "#82e6b1";
        default: return "#9db1ca";
    }
}


function techRange(
    candidates: Array<ThreatBeamCandidate | ThreatTorpedoCandidate>,
): string {
    const levels = candidates
        .map((candidate) => candidate.tech_level)
        .filter((level): level is number => level !== null);
    if (levels.length === 0) return "unknown";
    const minimum = Math.min(...levels);
    const maximum = Math.max(...levels);
    return minimum === maximum ? `T${minimum}` : `T${minimum}–T${maximum}`;
}


function candidateNames(
    candidates: Array<ThreatBeamCandidate | ThreatTorpedoCandidate>,
): string {
    if (candidates.length === 0) return "none compatible";
    if (candidates.length <= 4) return candidates.map((item) => item.name).join(", ");
    return `${candidates.slice(0, 3).map((item) => item.name).join(", ")} +${candidates.length - 3}`;
}


export function ThreatAnalysis({
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
    const [analysis, setAnalysis] = useState<ShipThreatAnalysis | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        async function load() {
            try {
                const response = await getShipThreatAnalysis(
                    gameId,
                    linkedAccountId,
                    turn,
                    shipId,
                );
                if (!cancelled) setAnalysis(response);
            } catch (reason) {
                if (!cancelled) {
                    setAnalysis(null);
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Threat analysis failed",
                    );
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        void load();
        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, shipId, turn]);

    const beamSummary = useMemo(() => {
        const candidates = analysis?.loadout?.beam_candidates ?? [];
        return `${techRange(candidates)} · ${candidateNames(candidates)}`;
    }, [analysis]);

    const torpedoSummary = useMemo(() => {
        const candidates = analysis?.loadout?.torpedo_candidates ?? [];
        return `${techRange(candidates)} · ${candidateNames(candidates)}`;
    }, [analysis]);

    if (loading) {
        return (
            <DetailSection title="Threat analysis">
                <p className="intel-no-facts">Analyzing observed threat…</p>
            </DetailSection>
        );
    }

    if (error !== null) {
        return (
            <DetailSection title="Threat analysis">
                <p className="intel-no-facts" style={{ color: "#ff9999" }}>
                    {error}
                </p>
            </DetailSection>
        );
    }

    if (analysis === null) return null;

    if (analysis.status === "catalog_missing") {
        return (
            <DetailSection title="Threat analysis">
                <p className="intel-no-facts">
                    {analysis.detail ?? "Game rules are not cached yet."}
                </p>
            </DetailSection>
        );
    }

    if (
        analysis.subject === undefined ||
        analysis.defense === undefined ||
        analysis.loadout === undefined ||
        analysis.subject.owner_slot_id === analysis.defense.primary_slot_id
    ) {
        return null;
    }

    const target = analysis.target ?? null;
    const vcr = analysis.loadout.vcr_reveal;
    const subjectMilitary = analysis.military?.subject_owner ?? null;
    const primaryMilitary = analysis.military?.primary_owner ?? null;

    return (
        <DetailSection title="Threat analysis · inference">
            <div
                style={{
                    padding: "8px 9px",
                    border: `1px solid ${riskColor(analysis.defense.risk)}66`,
                    borderRadius: 7,
                    background: `${riskColor(analysis.defense.risk)}12`,
                    marginBottom: 9,
                }}
            >
                <strong style={{ color: riskColor(analysis.defense.risk) }}>
                    {analysis.defense.risk.toUpperCase()}
                </strong>
                {analysis.defense.reasons.map((reason) => (
                    <div
                        key={reason}
                        style={{ color: "#c9d4e4", fontSize: 11, marginTop: 4 }}
                    >
                        {reason}
                    </div>
                ))}
            </div>

            <dl className="intel-fact-list">
                <FactRow label="Race" value={analysis.subject.race_name} />
                <FactRow label="Hull" value={analysis.subject.hull_name} />
                <FactRow label="Observed mass" value={analysis.subject.observed_mass ?? "—"} />
                <FactRow label="Bare hull mass" value={analysis.subject.hull_mass ?? "—"} />
                <FactRow
                    label="Hidden mass"
                    value={analysis.loadout.mass_excess_over_bare_hull ?? "—"}
                />
                <FactRow label="Beam slots" value={analysis.subject.beam_slots ?? "—"} />
                <FactRow label="Torpedo tubes" value={analysis.subject.tube_slots ?? "—"} />
            </dl>

            <div style={{ marginTop: 10 }}>
                <strong style={{ fontSize: 12 }}>Loadout constraints</strong>
                {vcr !== null ? (
                    <div className="intel-orbit-list" style={{ marginTop: 6 }}>
                        <div className="intel-orbit-item" style={{ cursor: "default" }}>
                            <span className="intel-orbit-symbol legend-orbit" />
                            <span>
                                <strong>VCR #{vcr.vcr_id} · T{vcr.battle_turn}</strong>
                                <small>
                                    factual equipment leak: {vcr.beam_count ?? "?"} beams · {vcr.launcher_count ?? "?"} tubes
                                </small>
                            </span>
                        </div>
                    </div>
                ) : (
                    <p className="intel-no-facts" style={{ marginTop: 5 }}>
                        No VCR equipment leak for this ship yet.
                    </p>
                )}
                <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                    <FactRow label="Beam candidates" value={beamSummary} />
                    <FactRow label="Torpedo candidates" value={torpedoSummary} />
                </dl>
                <p className="intel-no-facts" style={{ marginTop: 6 }}>
                    {analysis.loadout.mass_caveat}
                </p>
            </div>

            {analysis.race_traits !== undefined && analysis.race_traits.length > 0 && (
                <div style={{ marginTop: 10 }}>
                    <strong style={{ fontSize: 12 }}>Race capabilities</strong>
                    <div className="intel-orbit-list" style={{ marginTop: 5 }}>
                        {analysis.race_traits.map((trait) => (
                            <div
                                className="intel-orbit-item"
                                key={trait.name}
                                style={{ cursor: "default" }}
                            >
                                <span className="intel-orbit-symbol legend-orbit" />
                                <span>
                                    <strong>{trait.name}</strong>
                                    <small>
                                        {trait.active === true
                                            ? "active"
                                            : trait.active === false
                                                ? "disabled"
                                                : "game setting not resolved"}
                                        {" · "}{trait.basis}
                                    </small>
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{ marginTop: 10 }}>
                <strong style={{ fontSize: 12 }}>Likely objective</strong>
                {target === null ? (
                    <p className="intel-no-facts" style={{ marginTop: 5 }}>
                        No owned planet is close enough to the observed waypoint to infer a target.
                    </p>
                ) : (
                    <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                        <FactRow label="Target" value={target.name ?? `Planet #${target.planet_id}`} />
                        <FactRow label="Waypoint offset" value={target.waypoint_distance !== null ? `${target.waypoint_distance.toFixed(1)} ly` : "—"} />
                        <FactRow label="Distance" value={target.distance_from_ship !== null ? `${target.distance_from_ship.toFixed(1)} ly` : "—"} />
                        <FactRow label="ETA" value={target.eta_observed_turns === 1 ? "THIS HOST" : target.eta_observed_turns !== null ? `≈ ${target.eta_observed_turns} turns` : "—"} />
                        <FactRow label="Confidence" value={target.confidence.replace("_", " ")} />
                        <FactRow label="Defense posts" value={target.defense_posts ?? "—"} />
                        <FactRow label="Starbase" value={target.has_starbase ? "Yes" : "No"} />
                    </dl>
                )}
            </div>

            {(analysis.attack_group?.length ?? 0) > 1 && (
                <div style={{ marginTop: 10 }}>
                    <strong style={{ fontSize: 12 }}>
                        Attack group · {analysis.attack_group?.length}
                    </strong>
                    <div className="intel-orbit-list" style={{ marginTop: 5 }}>
                        {analysis.attack_group?.map((attacker) => (
                            <div
                                className="intel-orbit-item"
                                key={attacker.ship_id}
                                style={{ cursor: "default" }}
                            >
                                <span className="intel-orbit-symbol legend-orbit" />
                                <span>
                                    <strong>{attacker.name ?? `Ship #${attacker.ship_id}`}</strong>
                                    <small>
                                        #{attacker.ship_id} · mass {attacker.mass ?? "?"} · warp {attacker.warp ?? "?"}
                                    </small>
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{ marginTop: 10 }}>
                <strong style={{ fontSize: 12 }}>Reachable defense</strong>
                <div className="intel-orbit-list" style={{ marginTop: 5 }}>
                    {analysis.defense.defenders
                        .filter((defender) => defender.within_warp9_reach)
                        .slice(0, 8)
                        .map((defender) => (
                            <div
                                className="intel-orbit-item"
                                key={defender.ship_id}
                                style={{ cursor: "default" }}
                            >
                                <span className="intel-orbit-symbol legend-orbit" />
                                <span>
                                    <strong>{defender.name ?? `Ship #${defender.ship_id}`}</strong>
                                    <small>
                                        {defender.distance_to_target.toFixed(1)} ly · {defender.combat_hull ? "combat hull" : "non-combat"}
                                        {defender.tube_slots !== null && defender.tube_slots > 0
                                            ? ` · torps ${defender.torpedoes ?? "?"}`
                                            : ""}
                                        {defender.fighter_bays !== null && defender.fighter_bays > 0
                                            ? ` · fighters ${defender.fighters ?? "?"}`
                                            : ""}
                                    </small>
                                </span>
                            </div>
                        ))}
                </div>
                {analysis.defense.reachable_combat_defenders === 0 && (
                    <p className="intel-no-facts" style={{ marginTop: 5 }}>
                        No observed combat hull is within 81 ly of the inferred target.
                    </p>
                )}
            </div>

            {(subjectMilitary !== null || primaryMilitary !== null) && (
                <div style={{ marginTop: 10 }}>
                    <strong style={{ fontSize: 12 }}>Military context</strong>
                    <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                        <FactRow
                            label="Enemy military"
                            value={subjectMilitary !== null
                                ? `${subjectMilitary.military_score.toLocaleString()}${subjectMilitary.military_delta !== null ? ` · Δ ${subjectMilitary.military_delta >= 0 ? "+" : ""}${subjectMilitary.military_delta.toLocaleString()}` : ""}`
                                : "—"}
                        />
                        <FactRow
                            label="Primary military"
                            value={primaryMilitary !== null
                                ? `${primaryMilitary.military_score.toLocaleString()}${primaryMilitary.military_delta !== null ? ` · Δ ${primaryMilitary.military_delta >= 0 ? "+" : ""}${primaryMilitary.military_delta.toLocaleString()}` : ""}`
                                : "—"}
                        />
                    </dl>
                </div>
            )}

            <p className="intel-no-facts" style={{ marginTop: 10 }}>
                Read-time inference only. This is a readiness/threat estimate, not a combat simulator; factual observations remain unchanged.
            </p>
        </DetailSection>
    );
}
