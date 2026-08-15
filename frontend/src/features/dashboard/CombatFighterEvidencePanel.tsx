import { useEffect, useMemo, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
import type { GameDetailsResponse } from "../../types/api";
import type {
    CombatEquipmentEvidence,
    CombatEventSummary,
} from "../../types/history";

const MOBILE_FIGHTER_SCORE = 125;

type CombatDeltaBasis =
    | "review-confirmed"
    | "deterministic-replay"
    | "unresolved";

interface FighterCombatRow {
    key: string;
    vcrId: number;
    ownerId: number | null;
    ownerName: string;
    shipId: number;
    shipName: string;
    hullName: string;
    bays: number | null;
    startFighters: number;
    postFighters: number | null;
    postSource: string | null;
    deltaFighters: number | null;
    deltaMilitary: number | null;
    deltaBasis: CombatDeltaBasis;
    resultStatus: string;
}

interface OwnerCombatSummary {
    ownerId: number | null;
    ownerName: string;
    reviewConfirmedFighterDelta: number;
    reviewConfirmedMilitaryDelta: number;
    reviewConfirmedRows: number;
    replayFighterDelta: number;
    replayMilitaryDelta: number;
    replayRows: number;
}

function recordNumber(
    record: Record<string, unknown>,
    ...keys: string[]
): number | null {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, value] of Object.entries(record)) {
        if (!wanted.has(key.toLowerCase())) continue;
        if (typeof value === "number" && Number.isFinite(value)) return value;
    }
    return null;
}

function recordString(
    record: Record<string, unknown>,
    ...keys: string[]
): string | null {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    for (const [key, value] of Object.entries(record)) {
        if (!wanted.has(key.toLowerCase())) continue;
        if (typeof value === "string" && value.trim()) return value.trim();
    }
    return null;
}

function hullMap(catalog: GameRuleCatalogResponse | null) {
    const result = new Map<number, Record<string, unknown>>();
    for (const hull of catalog?.hulls ?? []) {
        const id = recordNumber(hull, "id");
        if (id !== null && Number.isInteger(id)) result.set(id, hull);
    }
    return result;
}

function fighterCount(equipment: CombatEquipmentEvidence): number | null {
    const value = equipment.combat_start_fighters ?? equipment.fighters;
    return typeof value === "number" && Number.isInteger(value) && value >= 0
        ? value
        : null;
}

function postFighterCount(equipment: CombatEquipmentEvidence): number | null {
    const value = equipment.post_combat_fighters;
    return typeof value === "number" && Number.isInteger(value) && value >= 0
        ? value
        : null;
}

function deltaBasis(
    source: string | null,
    postFighters: number | null,
): CombatDeltaBasis {
    if (postFighters === null) return "unresolved";
    if (source === "analyst_confirmed_vcr_review") return "review-confirmed";
    if (source === "deterministic_vcr_replay") return "deterministic-replay";
    return "unresolved";
}

function sourceLabel(source: string | null): string {
    if (source === "analyst_confirmed_vcr_review") return "analyst-confirmed";
    if (source === "deterministic_vcr_replay") return "deterministic replay";
    return source ?? "no post-combat evidence";
}

function deltaBasisLabel(basis: CombatDeltaBasis): string {
    if (basis === "review-confirmed") return "review-confirmed in-host delta";
    if (basis === "deterministic-replay") return "derived replay delta";
    return "not attributable";
}

function formatSigned(value: number): string {
    const rounded = Math.round(value);
    return `${rounded > 0 ? "+" : ""}${rounded.toLocaleString()}`;
}

export function CombatFighterEvidencePanel({
    game,
    linkedAccountId,
    turn,
}: {
    game: GameDetailsResponse;
    linkedAccountId: number;
    turn: number;
}) {
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [catalog, setCatalog] = useState<GameRuleCatalogResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        void Promise.all([
            getHistoricalCombatEvents(game.game.id, linkedAccountId, turn),
            getGameRuleCatalog(game.game.id),
        ]).then(([combat, rules]) => {
            if (cancelled) return;
            setEvents(combat.events);
            setCatalog(rules);
        }).catch((reason) => {
            if (!cancelled) {
                setError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load VCR fighter evidence",
                );
            }
        }).finally(() => {
            if (!cancelled) setLoading(false);
        });

        return () => {
            cancelled = true;
        };
    }, [game.game.id, linkedAccountId, turn]);

    const rows = useMemo<FighterCombatRow[]>(() => {
        const hulls = hullMap(catalog);
        const playerNames = new Map(
            game.players.map((player) => [player.slot_id, player.username]),
        );
        const result: FighterCombatRow[] = [];

        for (const event of events) {
            for (const side of event.sides) {
                if (side.object_kind !== "ship" || side.object_id === null) continue;
                const equipment = side.combat_equipment;
                if (equipment === null || equipment === undefined) continue;

                const startFighters = fighterCount(equipment);
                if (startFighters === null) continue;

                const hull = side.hull_id === null
                    ? undefined
                    : hulls.get(side.hull_id);
                const catalogBays = hull === undefined
                    ? null
                    : recordNumber(hull, "fighterbays", "bays");
                const vcrBays = equipment.bay_count;
                const bays = typeof vcrBays === "number"
                    ? vcrBays
                    : catalogBays;

                if ((bays ?? 0) <= 0 && startFighters <= 0) continue;

                const postFighters = postFighterCount(equipment);
                const postSource = equipment.post_combat_source ?? null;
                const basis = deltaBasis(postSource, postFighters);
                const fighterDelta = postFighters === null
                    ? null
                    : postFighters - startFighters;

                result.push({
                    key: `${event.vcr_id}:${side.side}:${side.object_id}`,
                    vcrId: event.vcr_id,
                    ownerId: side.owner_id,
                    ownerName: side.owner_id === null
                        ? "unknown owner"
                        : playerNames.get(side.owner_id) ?? `slot ${side.owner_id}`,
                    shipId: side.object_id,
                    shipName: side.name ?? `Ship #${side.object_id}`,
                    hullName: recordString(hull ?? {}, "name")
                        ?? (side.hull_id === null ? "Unknown hull" : `Hull #${side.hull_id}`),
                    bays: bays === null ? null : Math.max(0, Math.trunc(bays)),
                    startFighters,
                    postFighters,
                    postSource,
                    deltaFighters: fighterDelta,
                    deltaMilitary: fighterDelta === null
                        ? null
                        : fighterDelta * MOBILE_FIGHTER_SCORE,
                    deltaBasis: basis,
                    resultStatus: side.result_status,
                });
            }
        }

        result.sort((left, right) =>
            left.vcrId - right.vcrId
            || left.ownerName.localeCompare(right.ownerName)
            || left.shipId - right.shipId,
        );
        return result;
    }, [catalog, events, game.players]);

    const ownerSummaries = useMemo<OwnerCombatSummary[]>(() => {
        const byOwner = new Map<number | null, OwnerCombatSummary>();

        for (const row of rows) {
            if (row.deltaFighters === null || row.deltaMilitary === null) continue;

            const summary = byOwner.get(row.ownerId) ?? {
                ownerId: row.ownerId,
                ownerName: row.ownerName,
                reviewConfirmedFighterDelta: 0,
                reviewConfirmedMilitaryDelta: 0,
                reviewConfirmedRows: 0,
                replayFighterDelta: 0,
                replayMilitaryDelta: 0,
                replayRows: 0,
            };

            if (row.deltaBasis === "review-confirmed") {
                summary.reviewConfirmedFighterDelta += row.deltaFighters;
                summary.reviewConfirmedMilitaryDelta += row.deltaMilitary;
                summary.reviewConfirmedRows += 1;
            } else if (row.deltaBasis === "deterministic-replay") {
                summary.replayFighterDelta += row.deltaFighters;
                summary.replayMilitaryDelta += row.deltaMilitary;
                summary.replayRows += 1;
            }

            byOwner.set(row.ownerId, summary);
        }

        return [...byOwner.values()]
            .filter((summary) => summary.reviewConfirmedRows > 0 || summary.replayRows > 0)
            .sort((left, right) => left.ownerName.localeCompare(right.ownerName));
    }, [rows]);

    return (
        <section className="panel military-attribution-panel">
            <div className="panel-header">
                <div>
                    <h2>Combat fighter evidence · T{turn}</h2>
                    <p>
                        Fighter loads directly revealed by VCR combat. Combat-time
                        evidence stays separate from current ship observations; only
                        time-compatible in-host changes are classified as candidate
                        Military Δ evidence.
                    </p>
                </div>
            </div>

            {loading ? (
                <p className="muted">Loading combat loadout evidence…</p>
            ) : error !== null ? (
                <div className="error-box">{error}</div>
            ) : rows.length === 0 ? (
                <p className="muted">No fighter loads were revealed by accessible VCRs this turn.</p>
            ) : (
                <>
                    <div className="military-new-ships">
                        <h3>Time-compatible fighter deltas</h3>
                        {ownerSummaries.length === 0 ? (
                            <p className="muted">
                                No post-combat fighter state is available for attribution.
                            </p>
                        ) : (
                            ownerSummaries.map((summary) => (
                                <div
                                    className="military-new-ship-row"
                                    key={summary.ownerId ?? "unknown"}
                                >
                                    <div>
                                        <strong>{summary.ownerName}</strong>
                                        <small>combat events during host T{turn}</small>
                                    </div>
                                    <div>
                                        <span>Review-confirmed Δ</span>
                                        <strong>
                                            {summary.reviewConfirmedRows === 0
                                                ? "—"
                                                : `${formatSigned(summary.reviewConfirmedFighterDelta)} fighters`}
                                        </strong>
                                        <small>
                                            {summary.reviewConfirmedRows === 0
                                                ? "no analyst-confirmed post state"
                                                : `${formatSigned(summary.reviewConfirmedMilitaryDelta)} Military · ${summary.reviewConfirmedRows} VCR side(s)`}
                                        </small>
                                    </div>
                                    <div>
                                        <span>Replay-only Δ</span>
                                        <strong>
                                            {summary.replayRows === 0
                                                ? "—"
                                                : `${formatSigned(summary.replayFighterDelta)} fighters`}
                                        </strong>
                                        <small>
                                            {summary.replayRows === 0
                                                ? "no replay-only delta"
                                                : `${formatSigned(summary.replayMilitaryDelta)} Military · derived, not factual`}
                                        </small>
                                    </div>
                                </div>
                            ))
                        )}
                        <p className="muted">
                            Review-confirmed start→post changes occur inside this host and are
                            time-compatible with the turn delta. They are not automatically
                            folded into Confirmed factual Δ yet, because a directly comparable
                            turn-to-turn carrier snapshot may already contain the same loss.
                            Replay-only changes remain derived evidence and are never counted as facts.
                        </p>
                    </div>

                    <div className="military-new-ships">
                        <h3>VCR fighter observations</h3>
                        {rows.map((row) => (
                            <div className="military-new-ship-row" key={row.key}>
                                <div>
                                    <strong>#{row.shipId} {row.shipName}</strong>
                                    <small>
                                        {row.ownerName} · {row.hullName}
                                        {row.bays === null ? "" : ` · ${row.bays} bays`}
                                        {` · VCR #${row.vcrId}`}
                                    </small>
                                </div>
                                <div>
                                    <span>Combat start</span>
                                    <strong>{row.startFighters.toLocaleString()} fighters</strong>
                                    <small>factual VCR observation</small>
                                </div>
                                <div>
                                    <span>Post combat / in-host Δ</span>
                                    <strong>
                                        {row.postFighters === null
                                            ? "—"
                                            : `${row.postFighters.toLocaleString()} fighters`}
                                    </strong>
                                    <small>
                                        {row.deltaFighters === null || row.deltaMilitary === null
                                            ? `${sourceLabel(row.postSource)} · ${row.resultStatus.split("_").join(" ")}`
                                            : `${formatSigned(row.deltaFighters)} fighters · ${formatSigned(row.deltaMilitary)} Military · ${deltaBasisLabel(row.deltaBasis)}`}
                                    </small>
                                </div>
                            </div>
                        ))}
                        <p className="muted">
                            A combat-start fighter count proves that load only at the instant
                            of that VCR. It does not become the ship&apos;s current fighter count
                            and does not prove what the ship carried on the previous turn.
                        </p>
                    </div>
                </>
            )}
        </section>
    );
}
