import type { PublicArchiveTurn } from "../types/publicArchive";

export async function getPublicArchiveTurn(
    gameId: number,
    slotId: number,
    turn: number,
): Promise<PublicArchiveTurn> {
    const path = `/api/games/${gameId}/public-archive/turn?player_id=${slotId}&turn=${turn}`;
    const response = await fetch(path, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });
    if (!response.ok) {
        const detail = await response.json().catch(() => null) as {detail?: string} | null;
        throw new Error(detail?.detail ?? `Archive RST HTTP ${response.status}`);
    }
    return await response.json() as PublicArchiveTurn;
}
