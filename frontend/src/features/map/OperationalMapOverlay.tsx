import { useEffect, useState } from "react";

import { getHistoricalCombatEvents } from "../../api/history";
import type { CombatEventSummary } from "../../types/history";
import { HostEventPanel } from "./HostEventPanel";
import { PlayerActivityPanel } from "./PlayerActivityPanel";
import "./operational-shell.css";

type DrawerTab = "dashboard" | "combat";

function sideName(event: CombatEventSummary, index: 0 | 1): string {
    const side = event.sides[index];
    if (side.name !== null && side.name.trim()) return side.name;
    if (side.object_id !== null) {
        return side.object_kind === "ship"
            ? `Ship #${side.object_id}`
            : `Planet #${side.object_id}`;
    }
    return side.object_kind === "ship" ? "Unknown ship" : "Unknown planet";
}

export function OperationalMapOverlay({
    gameId,
    linkedAccountId,
    turn,
    onFocus,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    onFocus: (event: CombatEventSummary) => void;
}) {
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [tab, setTab] = useState<DrawerTab>("dashboard");
    const [events, setEvents] = useState<CombatEventSummary[]>([]);
    const [combatError, setCombatError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        void getHistoricalCombatEvents(gameId, linkedAccountId, turn)
            .then((response) => {
                if (cancelled) return;
                setEvents(response.events);
                setCombatError(null);
            })
            .catch((reason) => {
                if (cancelled) return;
                setEvents([]);
                setCombatError(
                    reason instanceof Error
                        ? reason.message
                        : "Failed to load combat events",
                );
            });

        return () => {
            cancelled = true;
        };
    }, [gameId, linkedAccountId, turn]);

    return (
        <>
            <div className="operational-map-chrome">
                <button
                    aria-label="Open dashboard"
                    className="operational-map-menu-button"
                    onClick={() => setDrawerOpen(true)}
                    type="button"
                >
                    <span aria-hidden="true">☰</span>
                </button>

                <button
                    className="operational-map-turn-button"
                    onClick={() => {
                        setTab("dashboard");
                        setDrawerOpen(true);
                    }}
                    type="button"
                >
                    Turn {turn}
                </button>

                {events.length > 0 && (
                    <button
                        className="operational-map-alert-button"
                        onClick={() => {
                            setTab("combat");
                            setDrawerOpen(true);
                        }}
                        type="button"
                    >
                        VCR {events.length}
                    </button>
                )}
            </div>

            {drawerOpen && (
                <div
                    className="operational-map-drawer-backdrop"
                    onMouseDown={(event) => {
                        if (event.currentTarget === event.target) {
                            setDrawerOpen(false);
                        }
                    }}
                >
                    <aside className="operational-map-drawer">
                        <header className="operational-map-drawer-header">
                            <div>
                                <span>Planets Intel</span>
                                <strong>Game #{gameId} · Turn {turn}</strong>
                            </div>
                            <button
                                aria-label="Close dashboard"
                                className="operational-map-drawer-close"
                                onClick={() => setDrawerOpen(false)}
                                type="button"
                            >
                                ×
                            </button>
                        </header>

                        <nav className="operational-map-drawer-tabs">
                            <button
                                className={tab === "dashboard" ? "is-active" : ""}
                                onClick={() => setTab("dashboard")}
                                type="button"
                            >
                                Dashboard
                            </button>
                            <button
                                className={tab === "combat" ? "is-active" : ""}
                                onClick={() => setTab("combat")}
                                type="button"
                            >
                                Combat
                                {events.length > 0 ? ` · ${events.length}` : ""}
                            </button>
                        </nav>

                        <div className="operational-map-drawer-body">
                            {tab === "dashboard" ? (
                                <>
                                    <section className="operational-map-drawer-section">
                                        <div className="operational-map-drawer-section-title">
                                            Current view
                                        </div>
                                        <p>
                                            The map is the primary workspace. Select a planet or
                                            ship to open its operational panel over the map.
                                        </p>
                                    </section>

                                    <section className="operational-map-drawer-section">
                                        <div className="operational-map-drawer-section-title">
                                            Host intelligence
                                        </div>
                                        <HostEventPanel
                                            gameId={gameId}
                                            linkedAccountId={linkedAccountId}
                                            turn={turn}
                                        />
                                    </section>

                                    <section className="operational-map-drawer-section">
                                        <div className="operational-map-drawer-section-title">
                                            Player activity
                                        </div>
                                        <PlayerActivityPanel
                                            gameId={gameId}
                                            throughTurn={turn}
                                        />
                                    </section>
                                </>
                            ) : (
                                <section className="operational-map-drawer-section">
                                    <div className="operational-map-drawer-section-title">
                                        Combat events · T{turn}
                                    </div>

                                    {combatError !== null && (
                                        <p className="operational-map-drawer-error">
                                            {combatError}
                                        </p>
                                    )}

                                    {combatError === null && events.length === 0 && (
                                        <p>No VCRs are stored for this turn.</p>
                                    )}

                                    <div className="operational-combat-list">
                                        {events.map((event) => (
                                            <button
                                                key={`${event.turn}:${event.vcr_id}`}
                                                onClick={() => {
                                                    onFocus(event);
                                                    setDrawerOpen(false);
                                                }}
                                                type="button"
                                            >
                                                <strong>
                                                    VCR #{event.vcr_id}
                                                </strong>
                                                <span>
                                                    {sideName(event, 0)} vs {sideName(event, 1)}
                                                </span>
                                                <small>
                                                    {event.x !== null && event.y !== null
                                                        ? `${event.x}, ${event.y}`
                                                        : "position unknown"}
                                                </small>
                                            </button>
                                        ))}
                                    </div>
                                </section>
                            )}
                        </div>
                    </aside>
                </div>
            )}
        </>
    );
}
