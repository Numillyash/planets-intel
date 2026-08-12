import type {
    LatestPrivateIntelResponse,
    PlanetObservationResponse,
    PrivateIntelCounts,
    PrivateIntelObserver,
    ShipObservationResponse,
    StarbaseObservationResponse,
    StellarCartographyObservationResponse,
} from "./api";

export interface DashboardIntelShareAccount {
    linked_account_id: number;
    planets_username: string;
    is_mine: boolean;
    is_active: boolean;
    approved: boolean;
}

export interface DashboardIntelShareResponse {
    id: number;
    status: "pending" | "active";
    account_a: DashboardIntelShareAccount;
    account_b: DashboardIntelShareAccount;
    created_at: string;
    updated_at: string;
}

export interface DashboardIntelSharesResponse {
    shares: DashboardIntelShareResponse[];
}

export interface DashboardIntelShareRevokeResponse {
    success: boolean;
}

export interface CombinedIntelSource {
    linked_account_id: number;
    planets_account_id: number | null;
    planets_username: string;
    player_slot_id: number;
    batch_id: number;
    turn: number;
    source: string;
    observed_at: string;
}

export interface IntelEntityProvenance {
    linked_account_id: number;
    planets_username: string;
    player_slot_id: number;
    batch_id: number;
    batch_turn: number;
    info_turn: number | null;
    observed_at: string;
}

interface CombinedEntityMetadata {
    selected_source_linked_account_id?: number;
    field_sources?: Record<string, number>;
    provenance?: IntelEntityProvenance[];
}

export type MapPlanetObservation = PlanetObservationResponse &
    CombinedEntityMetadata;

export type MapShipObservation = ShipObservationResponse &
    CombinedEntityMetadata;

export type MapStarbaseObservation = StarbaseObservationResponse &
    CombinedEntityMetadata;

export type MapStellarCartographyObservation =
    StellarCartographyObservationResponse & CombinedEntityMetadata;

export interface CombinedPrivateIntelResponse {
    mode: "combined";
    aggregation_policy: "freshest_field_union";
    game_id: number;
    turn: number;
    primary_observer: PrivateIntelObserver;
    sources: CombinedIntelSource[];
    counts: PrivateIntelCounts;
    planets: MapPlanetObservation[];
    ships: MapShipObservation[];
    starbases: MapStarbaseObservation[];
    stellar_cartography: MapStellarCartographyObservation[];
}

export type PrivateIntelMapResponse =
    | LatestPrivateIntelResponse
    | CombinedPrivateIntelResponse;

export function isCombinedPrivateIntel(
    intel: PrivateIntelMapResponse,
): intel is CombinedPrivateIntelResponse {
    return "mode" in intel && intel.mode === "combined";
}
