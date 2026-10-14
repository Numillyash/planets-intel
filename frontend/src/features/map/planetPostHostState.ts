import { useEffect, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import type { CombatEventResultStatus } from "../../types/history";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";

export interface PlanetPostHostState {
    ownerId: number;
    turn: number;
    vcrId: number;
    resultStatus: CombatEventResultStatus;
    basis: string | null;
}

export function usePlanetPostHostState(
    intel: PrivateIntelMapResponse,
    planetId: number,
): PlanetPostHostState | null {
    const [state, setState] = useState<PlanetPostHostState | null>(null);
    const linkedAccountId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.linked_account_id
        : intel.observer.linked_account_id;

    useEffect(() => {
        let active = true;
        setState(null);

        void getHistoricalCombatEvents(
            intel.game_id,
            linkedAccountId,
            intel.turn,
        )
            .then((response) => {
                if (!active) return;

                const matches = response.events
                    .flatMap((event) =>
                        event.sides.map((side) => ({ event, side })),
                    )
                    .filter(({ side }) =>
                        side.object_kind === "planet" &&
                        side.object_id === planetId &&
                        side.post_host_owner_id !== null &&
                        (
                            side.result_status === "planet_owner_changed_post_host" ||
                            side.result_status === "planet_held_post_host"
                        ),
                    )
                    .sort((left, right) =>
                        right.event.vcr_id - left.event.vcr_id,
                    );

                const latest = matches[0];
                if (latest === undefined || latest.side.post_host_owner_id === null) {
                    setState(null);
                    return;
                }

                setState({
                    ownerId: latest.side.post_host_owner_id,
                    turn: latest.event.turn,
                    vcrId: latest.event.vcr_id,
                    resultStatus: latest.side.result_status,
                    basis: latest.side.result_basis,
                });
            })
            .catch(() => {
                if (active) setState(null);
            });

        return () => {
            active = false;
        };
    }, [intel.game_id, intel.turn, linkedAccountId, planetId]);

    return state;
}
