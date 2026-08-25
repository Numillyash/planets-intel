import { useEffect, useMemo, useState } from "react";

import {
    getHistoricalCombatEvents,
    getHistoricalShipTracks,
} from "../../api/history";
import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
import type {
    GameDetailsResponse,
    ShipObservationResponse,
} from "../../types/api";
import type {
    CombatEquipmentEvidence,
    CombatEventSideSummary,
} from "../../types/history";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { factNumber, shipFacts } from "../map/observationView";
import { BattleSimulatorWorkbench } from "./BattleSimulatorWorkbench";
import "./battle-simulator.css";
import "./battle-simulator-workbench.css";
import "./battle-planner-inputs.css";

interface VcrShipCandidate {
    ship: ShipObservationResponse;
    turn: number;
    vcrId: number;
    equipment: CombatEquipmentEvidence | null;
}

const EQUIPMENT_FIELDS = {
    beams: ["beams", "beamcount", "beam_count"],
    beamId: ["beamid", "beam_id"],
    launchers: ["tubes", "torpedotubes", "tube_count", "launchercount", "launcher_count"],
    torpedoId: ["torpedoid", "torpedo_id"],
    bays: ["bays", "fighterbays", "baycount", "bay_count"],
} as const;

function nonNegativeNumber(value: unknown): number | null {
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
        return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number(value);
        if (Number.isFinite(parsed) && parsed >= 0) return parsed;
    }
    return null;
}

function payloadHasNumber(
    payload: Record<string, unknown>,
    keys: readonly string[],
): boolean {
    return keys.some((key) =>
        Object.prototype.hasOwnProperty.call(payload, key)
        && nonNegativeNumber(payload[key]) !== null,
    );
}

function positiveEquipmentValue(
    side: CombatEventSideSummary,
    key: keyof NonNullable<CombatEventSideSummary["combat_equipment"]>,
): number | null {
    const equipment = side.combat_equipment;
    if (equipment === null || equipment === undefined) return null;
    const value = equipment[key];
    return typeof value === "number" && Number.isFinite(value) && value >= 0
        ? value
        : null;
}

function vcrShipCandidate(
    side: CombatEventSideSummary,
    turn: number,
    vcrId: number,
): VcrShipCandidate | null {
    if (
        side.object_kind !== "ship" ||
        side.object_id === null ||
        side.hull_id === null ||
        side.hull_id <= 0
    ) {
        return null;
    }

    const payload: Record<string, unknown> = {
        simulatorintelbasis: "vcr_combat_observation",
        simulatorintelturn: turn,
        simulatorintelvcrid: vcrId,
    };

    const beams = positiveEquipmentValue(side, "beam_count");
    const beamId = positiveEquipmentValue(side, "beam_id");
    const launchers = positiveEquipmentValue(side, "launcher_count");
    const torpedoId = positiveEquipmentValue(side, "torpedo_id");
    const bays = positiveEquipmentValue(side, "bay_count");

    if (beams !== null) payload.beams = beams;
    if (beamId !== null) payload.beamid = beamId;
    if (launchers !== null) payload.tubes = launchers;
    if (torpedoId !== null) payload.torpedoid = torpedoId;
    if (bays !== null) payload.bays = bays;

    // VCR-only candidates preserve the old behavior: mutable combat-start
    // values are not presented as current ship facts. Existing current ships
    // are enriched separately below, with explicit evidence markers and only
    // when their current factual field is unavailable.
    return {
        ship: {
            ship_id: side.object_id,
            owner_id: side.owner_id,
            info_turn: turn,
            hull_id: side.hull_id,
            name: `${side.name ?? `Ship #${side.object_id}`} · VCR T${turn}`,
            x: null,
            y: null,
            warp: null,
            payload,
        },
        turn,
        vcrId,
        equipment: side.combat_equipment ?? null,
    };
}

function setEquipmentFallback(
    payload: Record<string, unknown>,
    aliases: readonly string[],
    targetKey: string,
    value: number | null,
): boolean {
    if (value === null || payloadHasNumber(payload, aliases)) return false;
    payload[targetKey] = value;
    return true;
}

function evidenceNumber(
    equipment: CombatEquipmentEvidence,
    key: keyof CombatEquipmentEvidence,
): number | null {
    return nonNegativeNumber(equipment[key]);
}

function mergeCurrentShipWithVcrEvidence<T extends ShipObservationResponse>(
    ship: T,
    candidate: VcrShipCandidate,
    plannerTurn: number,
): T {
    // Numeric ship ids are reused in long-running games. Never move evidence
    // across a factual hull/owner lifecycle boundary.
    if (
        ship.hull_id !== null
        && candidate.ship.hull_id !== null
        && ship.hull_id !== candidate.ship.hull_id
    ) {
        return ship;
    }
    if (
        ship.owner_id !== null
        && candidate.ship.owner_id !== null
        && ship.owner_id !== candidate.ship.owner_id
    ) {
        return ship;
    }

    const equipment = candidate.equipment;
    if (equipment === null) return ship;

    const payload: Record<string, unknown> = { ...ship.payload };
    let equipmentFilled = false;

    equipmentFilled = setEquipmentFallback(
        payload,
        EQUIPMENT_FIELDS.beams,
        "beams",
        evidenceNumber(equipment, "beam_count"),
    ) || equipmentFilled;
    equipmentFilled = setEquipmentFallback(
        payload,
        EQUIPMENT_FIELDS.beamId,
        "beamid",
        evidenceNumber(equipment, "beam_id"),
    ) || equipmentFilled;
    equipmentFilled = setEquipmentFallback(
        payload,
        EQUIPMENT_FIELDS.launchers,
        "tubes",
        evidenceNumber(equipment, "launcher_count"),
    ) || equipmentFilled;
    equipmentFilled = setEquipmentFallback(
        payload,
        EQUIPMENT_FIELDS.torpedoId,
        "torpedoid",
        evidenceNumber(equipment, "torpedo_id"),
    ) || equipmentFilled;
    equipmentFilled = setEquipmentFallback(
        payload,
        EQUIPMENT_FIELDS.bays,
        "bays",
        evidenceNumber(equipment, "bay_count"),
    ) || equipmentFilled;

    if (equipmentFilled) {
        payload.simulatorvcrequipmentturn = candidate.turn;
        payload.simulatorvcrequipmentvcrid = candidate.vcrId;
        payload.simulatorvcrequipmentbasis = "vcr_combat_observation";
    }

    // Mutable battle state is only eligible as a simulator default when the
    // latest VCR is from the planner turn. Current private/shared factual values
    // always win. Analyst-confirmed post state wins over deterministic replay;
    // if neither post state exists, combat-start ammunition is a last factual
    // fallback and is explicitly marked as historical combat-start evidence.
    if (candidate.turn === plannerTurn) {
        const currentFacts = shipFacts(ship);
        const postSource = typeof equipment.post_combat_source === "string"
            ? equipment.post_combat_source
            : null;
        const replaySurvived = equipment.replay_survived === true;
        let postFilled = false;
        let combatStartFilled = false;

        if (currentFacts.fighters === null) {
            const postFighters = evidenceNumber(equipment, "post_combat_fighters");
            if (
                postFighters !== null
                && postSource !== null
                && (postSource !== "deterministic_vcr_replay" || replaySurvived)
            ) {
                payload.fighters = postFighters;
                postFilled = true;
            } else {
                const startFighters = evidenceNumber(equipment, "combat_start_fighters")
                    ?? evidenceNumber(equipment, "fighters");
                if (startFighters !== null) {
                    payload.fighters = startFighters;
                    combatStartFilled = true;
                }
            }
        }

        if (currentFacts.torpedoes === null) {
            const postTorpedoes = evidenceNumber(equipment, "post_combat_torpedoes");
            if (
                postTorpedoes !== null
                && postSource !== null
                && (postSource !== "deterministic_vcr_replay" || replaySurvived)
            ) {
                payload.torpedoes = postTorpedoes;
                postFilled = true;
            } else {
                const startTorpedoes = evidenceNumber(equipment, "combat_start_torpedoes")
                    ?? evidenceNumber(equipment, "torpedoes");
                if (startTorpedoes !== null) {
                    payload.torpedoes = startTorpedoes;
                    combatStartFilled = true;
                }
            }
        }

        if (replaySurvived) {
            if (factNumber(ship.payload, "shield") === null) {
                const shield = evidenceNumber(equipment, "replay_post_combat_shield");
                if (shield !== null) {
                    payload.shield = shield;
                    postFilled = true;
                }
            }
            if (currentFacts.damage === null) {
                const damage = evidenceNumber(equipment, "replay_post_combat_damage");
                if (damage !== null) {
                    payload.damage = damage;
                    postFilled = true;
                }
            }
            if (currentFacts.crew === null) {
                const crew = evidenceNumber(equipment, "replay_post_combat_crew");
                if (crew !== null) {
                    payload.crew = crew;
                    postFilled = true;
                }
            }
        }

        if (postFilled) {
            payload.simulatorvcrpostturn = candidate.turn;
            payload.simulatorvcrpostvcrid = candidate.vcrId;
            payload.simulatorvcrpostbasis = postSource ?? "deterministic_vcr_replay";
        }
        if (combatStartFilled) {
            payload.simulatorvcrstartfallbackturn = candidate.turn;
            payload.simulatorvcrstartfallbackvcrid = candidate.vcrId;
        }
    }

    return {
        ...ship,
        payload,
    } as T;
}

function primaryLinkedAccountId(intel: PrivateIntelMapResponse): number {
    return isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;
}

export function StandaloneBattleSimulator({
    game,
    intel,
    turn,
}: {
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse | null;
    turn: number;
}) {
    const [catalog, setCatalog] = useState<GameRuleCatalogResponse | null>(null);
    const [catalogError, setCatalogError] = useState<string | null>(null);
    const [vcrCandidates, setVcrCandidates] = useState<VcrShipCandidate[]>([]);
    const [vcrSourceError, setVcrSourceError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setCatalog(null);
        setCatalogError(null);

        void getGameRuleCatalog(game.game.id)
            .then((response) => {
                if (!cancelled) setCatalog(response);
            })
            .catch((reason) => {
                if (cancelled) return;
                setCatalogError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load combat rule catalog",
                );
            });

        return () => {
            cancelled = true;
        };
    }, [game.game.id]);

    useEffect(() => {
        let cancelled = false;
        setVcrCandidates([]);
        setVcrSourceError(null);

        if (intel === null) {
            return () => {
                cancelled = true;
            };
        }

        const gameId = game.game.id;
        const linkedAccountId = primaryLinkedAccountId(intel);

        async function loadVcrCandidates() {
            try {
                const tracks = await getHistoricalShipTracks(
                    gameId,
                    linkedAccountId,
                    turn,
                );
                const combatTurns = Array.from(new Set([
                    turn,
                    ...tracks.tracks.flatMap((track) =>
                        track.points
                            .filter((point) => point.combat_event !== null)
                            .map((point) => point.turn),
                    ),
                ])).sort((left, right) => left - right);

                const eventResponses = await Promise.all(
                    combatTurns.map((combatTurn) =>
                        getHistoricalCombatEvents(
                            gameId,
                            linkedAccountId,
                            combatTurn,
                        ),
                    ),
                );

                const latest = new Map<number, VcrShipCandidate>();
                for (const response of eventResponses) {
                    for (const event of response.events) {
                        for (const side of event.sides) {
                            const candidate = vcrShipCandidate(
                                side,
                                event.turn,
                                event.vcr_id,
                            );
                            if (candidate === null) continue;

                            const previous = latest.get(candidate.ship.ship_id);
                            if (
                                previous === undefined ||
                                candidate.turn > previous.turn ||
                                (
                                    candidate.turn === previous.turn &&
                                    candidate.vcrId > previous.vcrId
                                )
                            ) {
                                latest.set(candidate.ship.ship_id, candidate);
                            }
                        }
                    }
                }

                if (!cancelled) {
                    setVcrCandidates(
                        Array.from(latest.values()).sort(
                            (left, right) => left.ship.ship_id - right.ship.ship_id,
                        ),
                    );
                }
            } catch (reason) {
                if (!cancelled) {
                    setVcrSourceError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load VCR-observed simulator ships",
                    );
                }
            }
        }

        void loadVcrCandidates();
        return () => {
            cancelled = true;
        };
    }, [game.game.id, intel, turn]);

    const simulatorIntel = useMemo<PrivateIntelMapResponse | null>(() => {
        if (intel === null || vcrCandidates.length === 0) return intel;

        const candidatesByShipId = new Map(
            vcrCandidates.map((candidate) => [candidate.ship.ship_id, candidate]),
        );
        const currentShipIds = new Set(intel.ships.map((ship) => ship.ship_id));
        const mergedCurrentShips = intel.ships.map((ship) => {
            const candidate = candidatesByShipId.get(ship.ship_id);
            return candidate === undefined
                ? ship
                : mergeCurrentShipWithVcrEvidence(ship, candidate, turn);
        });
        const vcrOnlyShips = vcrCandidates
            .filter((candidate) => !currentShipIds.has(candidate.ship.ship_id))
            .map((candidate) => candidate.ship);

        return {
            ...intel,
            ships: [...mergedCurrentShips, ...vcrOnlyShips],
        } as PrivateIntelMapResponse;
    }, [intel, turn, vcrCandidates]);

    if (simulatorIntel === null) {
        return (
            <div className="game-dashboard-empty">
                No private-intel snapshot is available for T{turn}.
            </div>
        );
    }

    if (catalogError !== null) {
        return <div className="error-card">{catalogError}</div>;
    }

    if (catalog === null) {
        return <div className="loading-card">Loading combat rule catalog…</div>;
    }

    return (
        <>
            {vcrSourceError !== null && (
                <div className="battle-sim-warning">
                    Current intel is available, but historical VCR ship sources could not be loaded: {vcrSourceError}
                </div>
            )}
            {vcrCandidates.length > 0 && (
                <div className="battle-sim-warning">
                    Missing known-ship simulator fields may be supplemented from accessible VCR evidence. Current private/shared facts win; VCR weapon setup is combat-time factual evidence, while deterministic post-combat values are derived simulator defaults and do not mutate canonical intel.
                </div>
            )}
            <BattleSimulatorWorkbench
                catalog={catalog}
                game={game}
                intel={simulatorIntel}
                turn={turn}
            />
        </>
    );
}
