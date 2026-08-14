import type {
    GameDetailsResponse,
    LatestPrivateIntelResponse,
} from "../../types/api";
import { formatInteger, starbaseFacts } from "../map/observationView";

function playerName(
    game: GameDetailsResponse,
    slotId: number | null,
): string {
    if (slotId === null) return "Unknown";
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} (slot ${slotId})` : `slot ${slotId}`;
}

export function StarbaseListPanel({
    game,
    intel,
}: {
    game: GameDetailsResponse;
    intel: LatestPrivateIntelResponse | null;
}) {
    const observerSlot = intel?.observer.player_slot_id ?? null;
    const starbases = intel?.starbases ?? [];

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Starbase List</h2>
                    <p>
                        {starbases.length} factual starbase observations.
                        Technology levels are shown only for bases owned by the
                        current observer in this snapshot.
                    </p>
                </div>
            </div>

            <div className="table-wrapper">
                <table className="players-table game-object-table">
                    <thead>
                        <tr>
                            <th>ID</th><th>Planet</th><th>Owner</th>
                            <th>Defense</th><th>Fighters</th>
                            <th>Beam tech</th><th>Engine tech</th>
                            <th>Hull tech</th><th>Torp tech</th>
                        </tr>
                    </thead>
                    <tbody>
                        {starbases.map((base) => {
                            const facts = starbaseFacts(base);
                            const planet = intel?.planets.find(
                                (item) => item.planet_id === base.planet_id,
                            ) ?? null;
                            const ownBase = observerSlot !== null
                                && planet?.owner_id === observerSlot;

                            return (
                                <tr
                                    className={ownBase ? "game-object-own" : undefined}
                                    key={base.starbase_id}
                                >
                                    <td>{base.starbase_id}</td>
                                    <td className="player-name">
                                        {planet?.name
                                            ?? (base.planet_id !== null
                                                ? `Planet #${base.planet_id}`
                                                : "—")}
                                    </td>
                                    <td>{playerName(game, planet?.owner_id ?? null)}</td>
                                    <td>{formatInteger(facts.defense)}</td>
                                    <td>{formatInteger(facts.fighters)}</td>
                                    <td>{ownBase ? facts.beamTech ?? "—" : "—"}</td>
                                    <td>{ownBase ? facts.engineTech ?? "—" : "—"}</td>
                                    <td>{ownBase ? facts.hullTech ?? "—" : "—"}</td>
                                    <td>{ownBase ? facts.torpedoTech ?? "—" : "—"}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
