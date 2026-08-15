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
    resultStatus: string;
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

function sourceLabel(source: string | null): string {
    if (source === "analyst_confirmed_vcr_review") return "analyst-confirmed";
    if (source === "deterministic_vcr_replay") return "deterministic replay";
    return source ?? "no post-combat evidence";
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
                    postFighters: postFighterCount(equipment),
                    postSource: equipment.post_combat_source ?? null,
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

    return (
        <section className="panel military-attribution-panel">
            <div className="panel-header">
                <div>
                    <h2>Combat fighter evidence · T{turn}</h2>
                    <p>
                        Fighter loads directly revealed by VCR combat. Combat-time
                        evidence stays separate from current ship observations and
                        is not silently deducted from Military Δ.
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
                <div className="military-new-ships">
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
                                <span>Post combat</span>
                                <strong>
                                    {row.postFighters === null
                                        ? "—"
                                        : `${row.postFighters.toLocaleString()} fighters`}
                                </strong>
                                <small>
                                    {sourceLabel(row.postSource)} · {row.resultStatus.split("_").join(" ")}
                                </small>
                            </div>
                        </div>
                    ))}
                    <p className="muted">
                        A combat-start fighter count proves that load at the instant
                        of that VCR. It does not by itself prove the same load at the
                        end of the host or on the previous turn.
                    </p>
                </div>
            )}
        </section>
    );
}
