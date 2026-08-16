import { useMemo, useState } from "react";

import type {
    GameDetailsResponse,
    ShipObservationResponse,
} from "../../types/api";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";
import { formatInteger, shipFacts } from "../map/observationView";

type ShipSort = "owner" | "id" | "name" | "hull" | "warp";

function playerName(
    game: GameDetailsResponse,
    slotId: number | null,
): string {
    if (slotId === null) return "Unknown";
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} (slot ${slotId})` : `slot ${slotId}`;
}

function observerSlot(intel: PrivateIntelMapResponse | null): number | null {
    if (intel === null) return null;
    return isCombinedPrivateIntel(intel)
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;
}

function compareNullableNumber(
    left: number | null,
    right: number | null,
): number {
    if (left === right) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return left - right;
}

export function StarshipListPanel({
    game,
    intel,
}: {
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse | null;
}) {
    const [sort, setSort] = useState<ShipSort>("owner");
    const currentObserverSlot = observerSlot(intel);

    const ships = useMemo(() => {
        const result = [...(intel?.ships ?? [])];

        result.sort((left, right) => {
            if (sort === "id") return left.ship_id - right.ship_id;
            if (sort === "name") {
                return (left.name ?? "").localeCompare(right.name ?? "")
                    || left.ship_id - right.ship_id;
            }
            if (sort === "hull") {
                return compareNullableNumber(left.hull_id, right.hull_id)
                    || left.ship_id - right.ship_id;
            }
            if (sort === "warp") {
                return compareNullableNumber(right.warp, left.warp)
                    || left.ship_id - right.ship_id;
            }

            const ownershipRank = (ship: ShipObservationResponse) => {
                if (
                    currentObserverSlot !== null
                    && ship.owner_id === currentObserverSlot
                ) return 0;
                if (ship.owner_id === null) return 2;
                return 1;
            };

            return ownershipRank(left) - ownershipRank(right)
                || compareNullableNumber(left.owner_id, right.owner_id)
                || left.ship_id - right.ship_id;
        });

        return result;
    }, [currentObserverSlot, intel, sort]);

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Starship List</h2>
                    <p>
                        {ships.length} factual ship observations. Own ships are
                        shown first by default.
                    </p>
                </div>

                <label className="dashboard-inline-control">
                    <span>Sort</span>
                    <select
                        className="secondary-button"
                        onChange={(event) =>
                            setSort(event.target.value as ShipSort)
                        }
                        value={sort}
                    >
                        <option value="owner">Owner / ID</option>
                        <option value="id">Ship ID</option>
                        <option value="name">Name</option>
                        <option value="hull">Hull ID</option>
                        <option value="warp">Warp</option>
                    </select>
                </label>
            </div>

            <div className="table-wrapper">
                <table className="players-table game-object-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>Ship</th><th>Owner</th><th>Hull</th>
                            <th>Warp</th><th>Fuel</th><th>Clans</th>
                            <th>Supplies</th><th>MC</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ships.map((ship) => {
                            const facts = shipFacts(ship);
                            const own = currentObserverSlot !== null
                                && ship.owner_id === currentObserverSlot;
                            return (
                                <tr
                                    className={own ? "game-object-own" : undefined}
                                    key={ship.ship_id}
                                >
                                    <td>{ship.ship_id}</td>
                                    <td className="player-name">
                                        {ship.name ?? `Ship ${ship.ship_id}`}
                                    </td>
                                    <td>{playerName(game, ship.owner_id)}</td>
                                    <td>{facts.hullName ?? ship.hull_id ?? "—"}</td>
                                    <td>{ship.warp ?? "—"}</td>
                                    <td>{formatInteger(facts.fuel)}</td>
                                    <td>{formatInteger(facts.clans)}</td>
                                    <td>{formatInteger(facts.supplies)}</td>
                                    <td>{formatInteger(facts.megacredits)}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
