import type {
    ShipOrderDraft,
    ShipOrderDraftUpdate,
} from "../types/orderDraft";


async function parseError(response: Response): Promise<string> {
    try {
        const payload = await response.json() as { detail?: string };
        if (payload.detail) return payload.detail;
    } catch {
        // fall through
    }
    return `${response.status} ${response.statusText}`;
}


function draftUrl(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): string {
    return `/api/games/${gameId}/order-drafts/ships/${shipId}`
        + `?turn=${turn}&linked_account_id=${linkedAccountId}`;
}


export async function getShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): Promise<ShipOrderDraft | null> {
    const response = await fetch(
        draftUrl(gameId, linkedAccountId, turn, shipId),
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (response.status === 404) return null;
    if (!response.ok) {
        throw new Error(`Order draft load failed: ${await parseError(response)}`);
    }
    return response.json() as Promise<ShipOrderDraft>;
}


export async function saveShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
    update: ShipOrderDraftUpdate,
): Promise<ShipOrderDraft> {
    const response = await fetch(
        draftUrl(gameId, linkedAccountId, turn, shipId),
        {
            method: "PUT",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(update),
        },
    );
    if (!response.ok) {
        throw new Error(`Order draft save failed: ${await parseError(response)}`);
    }
    return response.json() as Promise<ShipOrderDraft>;
}


export async function discardShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): Promise<void> {
    const response = await fetch(
        draftUrl(gameId, linkedAccountId, turn, shipId),
        {
            method: "DELETE",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok && response.status !== 404) {
        throw new Error(`Order draft discard failed: ${await parseError(response)}`);
    }
}
