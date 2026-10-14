import type {
    PlanetOrderDraft,
    ShipOrderDraft,
    ShipOrderDraftUpdate,
    StarbaseOrderDraft,
    StarbasePrimaryOrder,
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


function entityDraftUrl(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    kind: "ships" | "planets" | "starbases",
    entityId: number,
): string {
    return `/api/games/${gameId}/order-drafts/${kind}/${entityId}`
        + `?turn=${turn}&linked_account_id=${linkedAccountId}`;
}


async function getDraft<T>(url: string, label: string): Promise<T | null> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });
    if (response.status === 404) return null;
    if (!response.ok) {
        throw new Error(`${label} draft load failed: ${await parseError(response)}`);
    }
    return response.json() as Promise<T>;
}


async function saveDraft<T>(
    url: string,
    body: unknown,
    label: string,
): Promise<T> {
    const response = await fetch(url, {
        method: "PUT",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`${label} draft save failed: ${await parseError(response)}`);
    }
    return response.json() as Promise<T>;
}


async function discardDraft(url: string, label: string): Promise<void> {
    const response = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });
    if (!response.ok && response.status !== 404) {
        throw new Error(`${label} draft discard failed: ${await parseError(response)}`);
    }
}


export function getShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): Promise<ShipOrderDraft | null> {
    return getDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "ships", shipId),
        "Ship order",
    );
}


export function saveShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
    update: ShipOrderDraftUpdate,
): Promise<ShipOrderDraft> {
    return saveDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "ships", shipId),
        update,
        "Ship order",
    );
}


export function discardShipOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): Promise<void> {
    return discardDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "ships", shipId),
        "Ship order",
    );
}


export function getPlanetOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    planetId: number,
): Promise<PlanetOrderDraft | null> {
    return getDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "planets", planetId),
        "Planet order",
    );
}


export function savePlanetOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    planetId: number,
    friendlyCode: string,
): Promise<PlanetOrderDraft> {
    return saveDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "planets", planetId),
        { friendly_code: friendlyCode },
        "Planet order",
    );
}


export function discardPlanetOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    planetId: number,
): Promise<void> {
    return discardDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "planets", planetId),
        "Planet order",
    );
}


export function getStarbaseOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    starbaseId: number,
): Promise<StarbaseOrderDraft | null> {
    return getDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "starbases", starbaseId),
        "Starbase order",
    );
}


export function saveStarbaseOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    starbaseId: number,
    primaryOrder: StarbasePrimaryOrder,
): Promise<StarbaseOrderDraft> {
    return saveDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "starbases", starbaseId),
        { primary_order: primaryOrder },
        "Starbase order",
    );
}


export function discardStarbaseOrderDraft(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    starbaseId: number,
): Promise<void> {
    return discardDraft(
        entityDraftUrl(gameId, linkedAccountId, turn, "starbases", starbaseId),
        "Starbase order",
    );
}
