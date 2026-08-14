import { useEffect, useMemo, useState } from "react";

import { getShipOrderDraft } from "../../api/orderDraft";
import type { ShipOrderDraft } from "../../types/orderDraft";
import {
    isCombinedPrivateIntel,
    type PrivateIntelMapResponse,
} from "../../types/intel";


export function useMapOrderDrafts(
    intel: PrivateIntelMapResponse,
    linkedAccountId: number,
): ShipOrderDraft[] {
    const [drafts, setDrafts] = useState<ShipOrderDraft[]>([]);
    const [revision, setRevision] = useState(0);

    const primarySlotId = isCombinedPrivateIntel(intel)
        ? intel.primary_observer.player_slot_id
        : intel.observer.player_slot_id;

    const ownShipIds = useMemo(
        () => intel.ships
            .filter((ship) => ship.owner_id === primarySlotId)
            .map((ship) => ship.ship_id)
            .sort((left, right) => left - right),
        [intel.ships, primarySlotId],
    );

    useEffect(() => {
        const handleChanged = (event: Event) => {
            const detail = (event as CustomEvent<{
                gameId?: number;
                linkedAccountId?: number;
                turn?: number;
            }>).detail;
            if (
                detail?.gameId !== intel.game_id
                || detail?.linkedAccountId !== linkedAccountId
                || detail?.turn !== intel.turn
            ) {
                return;
            }
            setRevision((value) => value + 1);
        };

        window.addEventListener("intel-order-drafts-changed", handleChanged);
        return () => {
            window.removeEventListener("intel-order-drafts-changed", handleChanged);
        };
    }, [intel.game_id, intel.turn, linkedAccountId]);

    useEffect(() => {
        let cancelled = false;

        if (ownShipIds.length === 0) {
            setDrafts([]);
            return () => {
                cancelled = true;
            };
        }

        void Promise.all(
            ownShipIds.map(async (shipId) => {
                try {
                    return await getShipOrderDraft(
                        intel.game_id,
                        linkedAccountId,
                        intel.turn,
                        shipId,
                    );
                } catch {
                    // Historical turns intentionally reject write-context draft
                    // access. Treat those responses as "no local draft" here;
                    // the factual upstream vectors are still rendered.
                    return null;
                }
            }),
        ).then((values) => {
            if (cancelled) return;
            setDrafts(
                values.filter((value): value is ShipOrderDraft => value !== null),
            );
        });

        return () => {
            cancelled = true;
        };
    }, [
        intel.game_id,
        intel.turn,
        linkedAccountId,
        ownShipIds,
        revision,
    ]);

    return drafts;
}
