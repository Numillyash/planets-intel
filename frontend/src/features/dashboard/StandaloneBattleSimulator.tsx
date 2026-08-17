import { useEffect, useState } from "react";

import {
    getGameRuleCatalog,
    type GameRuleCatalogResponse,
} from "../../api/ruleCatalog";
import type { GameDetailsResponse } from "../../types/api";
import type { PrivateIntelMapResponse } from "../../types/intel";
import { BattleSimulatorWorkbench } from "./BattleSimulatorWorkbench";
import "./battle-simulator.css";
import "./battle-simulator-workbench.css";

export function StandaloneBattleSimulator({
    game,
    intel,
    turn,
}: {
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse | null;
    turn: number;
}) {
    const [catalog, setCatalog] = useState<GameRuleCatalogResponse | null>(null);
    const [catalogError, setCatalogError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setCatalog(null);
        setCatalogError(null);

        void getGameRuleCatalog(game.game.id)
            .then((response) => {
                if (!cancelled) setCatalog(response);
            })
            .catch((reason) => {
                if (cancelled) return;
                setCatalogError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load combat rule catalog",
                );
            });

        return () => {
            cancelled = true;
        };
    }, [game.game.id]);

    if (intel === null) {
        return (
            <div className="game-dashboard-empty">
                No private-intel snapshot is available for T{turn}.
            </div>
        );
    }

    if (catalogError !== null) {
        return <div className="error-card">{catalogError}</div>;
    }

    if (catalog === null) {
        return <div className="loading-card">Loading combat rule catalog…</div>;
    }

    return (
        <BattleSimulatorWorkbench
            catalog={catalog}
            game={game}
            intel={intel}
            turn={turn}
        />
    );
}
