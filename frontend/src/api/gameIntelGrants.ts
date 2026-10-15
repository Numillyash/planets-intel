/** Per-game consent records. This API does NOT grant access to peer snapshots. */
export type GameIntelMode = "native" | "unrestricted";

export type GameIntelScope =
    | "owned_unit_locations"
    | "third_party_contacts"
    | "combat_vcr_evidence"
    | "owned_planet_details"
    | "owned_ship_details"
    | "ship_friendly_codes"
    | "planet_friendly_codes"
    | "ship_orders"
    | "ship_transfers"
    | "starbase_orders_inventory"
    | "planet_build_goals"
    | "ship_history"
    | "wormhole_scans"
    | "private_messages"
    | "financial_and_cargo";

export interface GameIntelGrant {
    id: number;
    game_id: number;
    grantor_account_id: number;
    grantee_account_id: number;
    grantor_slot_id: number;
    grantee_slot_id: number;
    membership_verified_turn: number;
    requested_scopes: GameIntelScope[];
    sharing_mode: GameIntelMode;
    expanded_disclosure_confirmed_at: string | null;
    status: "pending" | "consented_pending_policy" | "revoked";
    authorizes_private_intel: false;
    consented_at: string | null;
    revoked_at: string | null;
    created_at: string;
    updated_at: string;
}

async function request<T>(path: string, body?: object): Promise<T> {
    const response = await fetch(path, {
        credentials: "same-origin",
        method: body ? "POST" : "GET",
        headers: {
            Accept: "application/json",
            ...(body ? { "Content-Type": "application/json" } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
        let detail = response.status + " " + response.statusText;
        try {
            const payload = await response.json() as { detail?: string };
            detail = payload.detail ?? detail;
        } catch {
            // Keep HTTP status if the server returned a non-JSON failure.
        }
        throw new Error(detail);
    }
    return response.json() as Promise<T>;
}

export async function getGameIntelGrants(gameId: number): Promise<GameIntelGrant[]> {
    const response = await request<{ grants: GameIntelGrant[] }>(
        "/api/intel/games/" + gameId + "/grants",
    );
    return response.grants;
}

export function requestGameIntelGrant(
    gameId: number,
    grantorAccountId: number,
    targetUsername: string,
    mode: GameIntelMode,
    requestedScopes: GameIntelScope[],
): Promise<GameIntelGrant> {
    return request<GameIntelGrant>("/api/intel/games/" + gameId + "/grants", {
        grantor_account_id: grantorAccountId,
        grantee_planets_username: targetUsername,
        sharing_mode: mode,
        requested_scopes: requestedScopes,
    });
}

export function consentGameIntelGrant(
    gameId: number,
    grantId: number,
    linkedAccountId: number,
    confirmUnrestricted: boolean,
): Promise<GameIntelGrant> {
    return request<GameIntelGrant>(
        "/api/intel/games/" + gameId + "/grants/" + grantId + "/consent",
        {
            grantee_account_id: linkedAccountId,
            confirm_unrestricted: confirmUnrestricted,
        },
    );
}

export function revokeGameIntelGrant(
    gameId: number,
    grantId: number,
    linkedAccountId: number,
): Promise<GameIntelGrant> {
    return request<GameIntelGrant>(
        "/api/intel/games/" + gameId + "/grants/" + grantId + "/revoke",
        { account_id: linkedAccountId },
    );
}

export interface GameIntelGrantPreview {
    game_id: number;
    grant_id: number;
    mode: GameIntelMode;
    turn: number;
    source_batch_id: number | null;
    preview_only: true;
    planets: Array<{ planet_id: number; fields: Record<string, unknown> }>;
    ships: Array<{ ship_id: number; fields: Record<string, unknown> }>;
    starbases: Array<{ starbase_id: number; fields: Record<string, unknown> }>;
    messages: Array<Record<string, unknown>>;
    combat_events: Array<Record<string, unknown>>;
    third_party_contacts: Array<Record<string, unknown>>;
}

export function getGameIntelGrantPreview(
    gameId: number,
    grantId: number,
    grantorAccountId: number,
): Promise<GameIntelGrantPreview> {
    return request<GameIntelGrantPreview>(
        "/api/intel/games/" + gameId + "/grants/" + grantId +
        "/preview?linked_account_id=" + grantorAccountId,
    );
}
export interface ScopedPartnerIntelSource {
    grant_id: number;
    source_linked_account_id: number;
    source_player_slot_id: number;
    source_batch_id: number;
    source_observed_at: string;
    requested_scopes: GameIntelScope[];
    planets: Array<{
        planet_id: number;
        owner_id: number;
        info_turn: number | null;
        fields: Record<string, unknown>;
    }>;
    ships: Array<{
        ship_id: number;
        owner_id: number;
        info_turn: number | null;
        fields: Record<string, unknown>;
    }>;
    starbases: Array<{
        starbase_id: number;
        planet_id: number | null;
        info_turn: number | null;
        fields: Record<string, unknown>;
    }>;
    third_party_contacts: Array<{
        kind: "planet" | "ship";
        id: number;
        owner_id: number | null;
        info_turn: number | null;
        x: number | null;
        y: number | null;
    }>;
    messages: Array<Record<string, unknown>>;
    combat_events: Array<Record<string, unknown>>;
}

export interface ScopedPartnerIntel {
    game_id: number;
    turn: number;
    primary_linked_account_id: number;
    mode: "scoped_partner_intel";
    aggregation_policy: "source_separated_allowlisted_current_turn";
    sources: ScopedPartnerIntelSource[];
}

export function getReceivedGameIntel(
    gameId: number,
    linkedAccountId: number,
): Promise<ScopedPartnerIntel> {
    return request<ScopedPartnerIntel>(
        "/api/intel/games/" + gameId + "/received?linked_account_id=" + linkedAccountId,
    );
}

