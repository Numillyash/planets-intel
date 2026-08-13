import type { ShipThreatAnalysis } from "../types/threat";


async function parseErrorMessage(response: Response): Promise<string> {
    try {
        const body = await response.json() as { detail?: string };
        if (typeof body.detail === "string" && body.detail.trim()) {
            return body.detail;
        }
    } catch {
        // Ignore non-JSON errors and fall through to status text.
    }
    return `${response.status} ${response.statusText}`;
}


export async function getShipThreatAnalysis(
    gameId: number,
    linkedAccountId: number,
    turn: number,
    shipId: number,
): Promise<ShipThreatAnalysis> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/analysis/ship-threat/${shipId}`
        + `?linked_account_id=${linkedAccountId}&turn=${turn}`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );
    if (!response.ok) {
        throw new Error(
            `Threat analysis failed: ${await parseErrorMessage(response)}`,
        );
    }
    return response.json() as Promise<ShipThreatAnalysis>;
}
