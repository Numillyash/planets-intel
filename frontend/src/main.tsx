import React, {
    useEffect,
    useMemo,
    useState,
} from "react";

import ReactDOM from "react-dom/client";

import {
    getGame,
    getScoreHistory,
} from "./api/client";

import { PlayersTable } from "./features/players/PlayersTable";
import { MilitaryScoreChart } from "./features/statistics/MilitaryScoreChart";

import type {
    GameDetailsResponse,
    ScoreHistoryResponse,
} from "./types/api";

import "./styles.css";


const GAME_ID = 680933;


function App() {
    const [game, setGame] =
        useState<GameDetailsResponse | null>(
            null,
        );

    const [history, setHistory] =
        useState<ScoreHistoryResponse | null>(
            null,
        );

    const [error, setError] =
        useState<string | null>(null);

    const [loading, setLoading] =
        useState(true);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                const [
                    gameResponse,
                    historyResponse,
                ] = await Promise.all([
                    getGame(GAME_ID),
                    getScoreHistory(GAME_ID),
                ]);

                if (cancelled) {
                    return;
                }

                setGame(gameResponse);
                setHistory(historyResponse);
            } catch (reason) {
                if (cancelled) {
                    return;
                }

                setError(
                    reason instanceof Error
                        ? reason.message
                        : "Unknown error",
                );
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void load();

        return () => {
            cancelled = true;
        };
    }, []);

    const latestScores = useMemo(() => {
        const result = new Map<number, ScoreHistoryResponse["items"][number]>();

        if (!history) {
            return result;
        }

        for (const item of history.items) {
            const current = result.get(
                item.slot_id,
            );

            if (
                !current ||
                item.turn > current.turn
            ) {
                result.set(
                    item.slot_id,
                    item,
                );
            }
        }

        return result;
    }, [history]);

    if (loading) {
        return (
            <main className="app-shell centered-state">
                <div className="loading-card">
                    Loading Planets.nu intelligence…
                </div>
            </main>
        );
    }

    if (error || !game || !history) {
        return (
            <main className="app-shell centered-state">
                <div className="error-card">
                    <h1>Failed to load game</h1>
                    <p>
                        {error ??
                            "Game data is unavailable."}
                    </p>
                </div>
            </main>
        );
    }

    return (
        <main className="app-shell">
            <header className="topbar">
                <div>
                    <div className="eyebrow">
                        Planets.nu Intel
                    </div>

                    <h1>
                        {game.game.name}
                    </h1>

                    <p className="subtitle">
                        {
                            game.game
                                .short_description
                        }
                    </p>
                </div>

                <div className="game-status">
                    <span className="status-badge">
                        {
                            game.game
                                .status_name
                        }
                    </span>

                    <strong>
                        Turn{" "}
                        {game.game.turn}
                    </strong>

                    <span>
                        {game.game.slots}{" "}
                        slots
                    </span>
                </div>
            </header>

            <section className="summary-grid">
                <div className="summary-card">
                    <span>Planets</span>
                    <strong>
                        {
                            game.settings
                                .num_planets
                        }
                    </strong>
                </div>

                <div className="summary-card">
                    <span>Ship limit</span>
                    <strong>
                        {
                            game.settings
                                .ship_limit
                        }
                    </strong>
                </div>

                <div className="summary-card">
                    <span>Schedule</span>
                    <strong>
                        {game.schedule}
                    </strong>
                </div>

                <div className="summary-card">
                    <span>Next host</span>
                    <strong>
                        {game.time_to_host}
                    </strong>
                </div>
            </section>

            <PlayersTable
                players={game.players}
                latestScores={
                    latestScores
                }
            />

            <MilitaryScoreChart
                players={game.players}
                history={history.items}
            />
        </main>
    );
}


ReactDOM
    .createRoot(
        document.getElementById(
            "root",
        )!,
    )
    .render(
        <React.StrictMode>
            <App />
        </React.StrictMode>,
    );
