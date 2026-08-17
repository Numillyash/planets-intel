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
import type { CombatEventSideSummary } from "../../types/history";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { BattleSimulatorWorkbench } from "./BattleSimulatorWorkbench";
import "./battle-simulator.css";
import "./battle-simulator-workbench.css";
import "./battle-planner-inputs.css";

interface VcrShipCandidate {
    ship: ShipObservationResponse;
    turn: number;
    vcrId: number;
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

    // VCR shield/damage/crew/ammo are factual only at combat time. Do not copy
    // those mutable values into the active simulator-known-ship state: leaving
    // them absent makes the editor expose explicit simulation assumptions.
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
    };
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
    const [vcrShips, setVcrShips] = useState<ShipObservationResponse[]>([]);
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
        setVcrShips([]);
        setVcrSourceError(null);

        if (intel === null) {
            return () => {
                cancelled = true;
            };
        }

        const gameId = game.game.id;
        const linkedAccountId = primaryLinkedAccountId(intel);
        const currentShipIds = new Set(intel.ships.map((ship) => ship.ship_id));

        async function loadVcrShips() {
            try {
                const tracks = await getHistoricalShipTracks(
                    gameId,
                    linkedAccountId,
                    turn,
                );
                const combatTurns = Array.from(new Set(
                    tracks.tracks.flatMap((track) =>
                        track.points
                            .filter((point) => point.combat_event !== null)
                            .map((point) => point.turn),
                    ),
                )).sort((left, right) => left - right);

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
                            if (
                                candidate === null ||
                                currentShipIds.has(candidate.ship.ship_id)
                            ) {
                                continue;
                            }

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
                    setVcrShips(
                        Array.from(latest.values())
                            .sort((left, right) => left.ship.ship_id - right.ship.ship_id)
                            .map((candidate) => candidate.ship),
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

        void loadVcrShips();
        return () => {
            cancelled = true;
        };
    }, [game.game.id, intel, turn]);

    const simulatorIntel = useMemo<PrivateIntelMapResponse | null>(() => {
        if (intel === null || vcrShips.length === 0) return intel;
        return {
            ...intel,
            ships: [...intel.ships, ...vcrShips],
        } as PrivateIntelMapResponse;
    }, [intel, vcrShips]);

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
            <BattleSimulatorWorkbench
                catalog={catalog}
                game={game}
                intel={simulatorIntel}
                turn={turn}
            />
        </>
    );
}
