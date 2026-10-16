import { useState } from "react";

import { CommanderIntelligencePanel } from "./CommanderIntelligencePanel";
import "./intelboard-game-picker.css";

export function PublicSectorExplorer({ gameId }: { gameId: number }) {
    const [sectorInput, setSectorInput] = useState(String(gameId));

    return (
        <main className="intelboard-public-sector-view">
            <section className="intelboard-public-sector-entry">
                <div>
                    <div className="eyebrow">PUBLIC-ONLY HISTORICAL ANALYSIS</div>
                    <h1>Explore sector #{gameId}</h1>
                    <p>
                        Public games only. This initial release shows prior
                        encounters for attributable current participants.
                        No private observations, orders or linked observer are used.
                        Former/replaced participants require a later roster-history expansion.
                    </p>
                    <p><a href="/intelboard">← Back to my games</a></p>
                </div>
                <form onSubmit={(event) => {
                    event.preventDefault();
                    const nextId = Number(sectorInput.trim());
                    if (Number.isSafeInteger(nextId) && nextId > 0) {
                        window.location.assign(`/intelboard/public/${nextId}`);
                    }
                }}>
                    <label htmlFor="explorer-sector-id">Game ID</label>
                    <input
                        id="explorer-sector-id"
                        min={1}
                        step={1}
                        type="number"
                        value={sectorInput}
                        required
                        onChange={(event) => setSectorInput(event.target.value)}
                    />
                    <button
                        type="submit"
                        className="primary-button"
                        disabled={!Number.isSafeInteger(Number(sectorInput.trim()))
                            || Number(sectorInput.trim()) <= 0}
                    >
                        Analyze
                    </button>
                </form>
            </section>
            <CommanderIntelligencePanel gameId={gameId} publicMode />
        </main>
    );
}
