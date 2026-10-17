import type {
    PlanetObservationResponse,
    ShipObservationResponse,
    StarbaseObservationResponse,
    StellarCartographyObservationResponse,
} from "./api";

export interface PublicArchiveTurn {
    mode: "public_finished_archive";
    source: string;
    game_id: number;
    turn: number;
    player_slot_id: number;
    counts: {
        planets: number;
        ships: number;
        starbases: number;
    };
    planets: PlanetObservationResponse[];
    ships: ShipObservationResponse[];
    starbases: StarbaseObservationResponse[];
    stellar_cartography: StellarCartographyObservationResponse[];
}
