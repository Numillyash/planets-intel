import type { GameDetailsResponse } from "../../types/api";

const RELATION_LABELS = new Map<number, string>([
    [-1, "Blocked Communications"],
    [0, "None"],
    [1, "Send Ambassador"],
    [2, "Safe Passage"],
    [3, "Share Intel"],
    [4, "Full Alliance"],
]);

function playerLabel(
    game: GameDetailsResponse,
    slotId: number,
): string {
    const player = game.players.find((item) => item.slot_id === slotId);
    return player ? `${player.username} · slot ${slotId}` : `slot ${slotId}`;
}

function relationLabel(value: number): string {
    const named = RELATION_LABELS.get(value);
    return named === undefined ? `Unknown code ${value}` : `${named} · ${value}`;
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
                        Relations for {playerLabel(game, observerSlotId)}.
                        `relation_to` is your outgoing setting; `relation_from`
                        is the other player's setting toward you. Known Nu codes
                        are named below; unknown values remain explicit rather
                        than being guessed.
                    </p>
                </div>
            </div>

            <div className="loading-card" style={{ marginBottom: 12 }}>
                Planets.nu diplomacy is read-only in IntelBoard right now. Changing Share Intel,
                Safe Passage, Full Alliance, or other Nu relations is not sent upstream until the
                current /game/save relation serialization has been captured and verified.
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
                                    <dd>{relationLabel(relation.relation_to)}</dd>
                                </div>
                                <div>
                                    <dt>Them → you</dt>
                                    <dd>{relationLabel(relation.relation_from)}</dd>
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
