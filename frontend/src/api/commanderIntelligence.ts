import type { CommanderIntelligenceResponse } from "../types/commanderIntelligence";


async function parseErrorMessage(response: Response): Promise<string> {
    try {
        const body = await response.json() as { detail?: string };
        if (typeof body.detail === "string" && body.detail.trim()) {
            return body.detail;
        }
    } catch {
        // Fall through to status text.
    }
    return `${response.status} ${response.statusText}`;
}


export async function getCommanderIntelligence(
    gameId: number,
): Promise<CommanderIntelligenceResponse> {
    const response = await fetch(
        `/api/games/${gameId}/commander-intelligence`,
        {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        },
    );

    if (!response.ok) {
        throw new Error(
            `Commander intelligence failed: ${await parseErrorMessage(response)}`,
        );
    }

    return response.json() as Promise<CommanderIntelligenceResponse>;
}
