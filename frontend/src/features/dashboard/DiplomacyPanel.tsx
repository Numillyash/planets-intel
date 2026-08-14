import type { GameDetailsResponse } from "../../types/api";

function playerLabel(
    game: GameDetailsResponse,
    slotId: number,
): string {
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} · slot ${slotId}` : `slot ${slotId}`;
}

export function DiplomacyPanel({
    game,
    observerSlotId,
}: {
    game: GameDetailsResponse;
    observerSlotId: number | null;
}) {
    if (observerSlotId === null) {
        return (
            <section className="panel">
                <div className="panel-header">
                    <div>
                        <h2>Diplomacy</h2>
                        <p>Observer player slot is unavailable.</p>
                    </div>
                </div>
            </section>
        );
    }

    const rows = game.players
        .filter((player) => player.slot_id !== observerSlotId)
        .map((player) => ({
            player,
            relation: game.relations.find(
                (relation) =>
                    relation.player_id === observerSlotId
                    && relation.player_to_id === player.slot_id,
            ) ?? null,
        }));

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Diplomacy</h2>
                    <p>
                        Relations from {playerLabel(game, observerSlotId)} only.
                        Raw Nu relation codes are retained until a named-status
                        mapping is explicitly validated.
                    </p>
                </div>
            </div>

            <div className="diplomacy-cards">
                {rows.map(({ player, relation }) => (
                    <article
                        className="diplomacy-card"
                        key={player.slot_id}
                    >
                        <div>
                            <strong>{player.username}</strong>
                            <span>slot {player.slot_id}</span>
                        </div>

                        {relation === null ? (
                            <span className="diplomacy-unknown">
                                No canonical relation record
                            </span>
                        ) : (
                            <dl>
                                <div>
                                    <dt>You → them</dt>
                                    <dd>{relation.relation_from}</dd>
                                </div>
                                <div>
                                    <dt>Them → you</dt>
                                    <dd>{relation.relation_to}</dd>
                                </div>
                                <div>
                                    <dt>Conflict</dt>
                                    <dd>{relation.conflict_level}</dd>
                                </div>
                            </dl>
                        )}
                    </article>
                ))}
            </div>
        </section>
    );
}
