import type { PlayerInfo } from "../types/api";


export interface RaceVisual {
    id: number;
    name: string;
    color: number;
    cssColor: string;
}


// Fixed categorical palette for the eleven classic races.  The mapping is
// intentionally race-based rather than player-slot-based so the same race has
// the same visual identity in every game and for every observer.
export const RACES: readonly RaceVisual[] = [
    { id: 1, name: "Federation", color: 0x4d7cfe, cssColor: "#4D7CFE" },
    { id: 2, name: "Lizards", color: 0x2fd566, cssColor: "#2FD566" },
    { id: 3, name: "Bird Men", color: 0xb56cff, cssColor: "#B56CFF" },
    { id: 4, name: "Fascists", color: 0xff4055, cssColor: "#FF4055" },
    { id: 5, name: "Privateers", color: 0xff4db8, cssColor: "#FF4DB8" },
    { id: 6, name: "Cyborg", color: 0x00d8e8, cssColor: "#00D8E8" },
    { id: 7, name: "Crystal People", color: 0xf4f7ff, cssColor: "#F4F7FF" },
    { id: 8, name: "Evil Empire", color: 0xff7a21, cssColor: "#FF7A21" },
    { id: 9, name: "Robots", color: 0x00a88f, cssColor: "#00A88F" },
    { id: 10, name: "Rebels", color: 0xa8e63c, cssColor: "#A8E63C" },
    { id: 11, name: "Colonies", color: 0xffdf3a, cssColor: "#FFDF3A" },
] as const;


const RACE_BY_ID = new Map(
    RACES.map((race) => [race.id, race]),
);


export function raceVisual(
    raceId: number | null | undefined,
): RaceVisual | null {
    if (raceId === null || raceId === undefined) {
        return null;
    }

    return RACE_BY_ID.get(raceId) ?? null;
}


export function raceName(raceId: number): string {
    return raceVisual(raceId)?.name ?? `Race ${raceId}`;
}


export function raceVisualForOwner(
    ownerSlotId: number | null,
    players: PlayerInfo[],
): RaceVisual | null {
    if (ownerSlotId === null || ownerSlotId <= 0) {
        return null;
    }

    const player = players.find(
        (candidate) => candidate.slot_id === ownerSlotId,
    );

    return player ? raceVisual(player.race_id) : null;
}
