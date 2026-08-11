import React, {
    type FormEvent,
    useEffect,
    useMemo,
    useState,
} from "react";

import ReactDOM from "react-dom/client";

import {
    getCurrentUser,
    getGame,
    getScoreHistory,
    login,
    logout,
} from "./api/client";

import { PlayersTable } from "./features/players/PlayersTable";
import { MilitaryScoreChart } from "./features/statistics/MilitaryScoreChart";

import type {
    CurrentUserResponse,
    GameDetailsResponse,
    ScoreHistoryResponse,
} from "./types/api";

import "./styles.css";


const GAME_ID = 680933;


interface LoginScreenProps {
    onLogin: (
        username: string,
        password: string,
    ) => Promise<void>;
}


function LoginScreen({
    onLogin,
}: LoginScreenProps) {
    const [username, setUsername] =
        useState("");
    const [password, setPassword] =
        useState("");
    const [error, setError] =
        useState<string | null>(null);
    const [submitting, setSubmitting] =
        useState(false);

    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();

        setSubmitting(true);
        setError(null);

        try {
            await onLogin(
                username.trim(),
                password,
            );
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Login failed",
            );
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="auth-page">
            <section className="auth-card">
                <div className="eyebrow">
                    Planets.nu Intel
                </div>

                <h1>Sign in</h1>

                <p className="auth-subtitle">
                    Use your local Intel Client account.
                </p>

                <form
                    className="auth-form"
                    onSubmit={handleSubmit}
                >
                    <label>
                        <span>Username</span>
                        <input
                            autoComplete="username"
                            autoFocus
                            disabled={submitting}
                            name="username"
                            onChange={(event) => {
                                setUsername(
                                    event.target.value,
                                );
                            }}
                            required
                            type="text"
                            value={username}
                        />
                    </label>

                    <label>
                        <span>Password</span>
                        <input
                            autoComplete="current-password"
                            disabled={submitting}
                            name="password"
                            onChange={(event) => {
                                setPassword(
                                    event.target.value,
                                );
                            }}
                            required
                            type="password"
                            value={password}
                        />
                    </label>

                    {error && (
                        <div
                            className="auth-error"
                            role="alert"
                        >
                            {error}
                        </div>
                    )}

                    <button
                        className="primary-button"
                        disabled={
                            submitting ||
                            !username.trim() ||
                            !password
                        }
                        type="submit"
                    >
                        {submitting
                            ? "Signing in…"
                            : "Sign in"}
                    </button>
                </form>
            </section>
        </main>
    );
}


interface DashboardProps {
    user: CurrentUserResponse;
    onLogout: () => Promise<void>;
}


function Dashboard({
    user,
    onLogout,
}: DashboardProps) {
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

    const [loggingOut, setLoggingOut] =
        useState(false);

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

    async function handleLogout() {
        setLoggingOut(true);

        try {
            await onLogout();
        } finally {
            setLoggingOut(false);
        }
    }

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

                <div className="topbar-actions">
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

                    <div className="user-menu">
                        <div>
                            <span className="user-label">
                                Signed in as
                            </span>
                            <strong>
                                {user.display_name}
                            </strong>
                        </div>

                        <button
                            className="secondary-button"
                            disabled={loggingOut}
                            onClick={() => {
                                void handleLogout();
                            }}
                            type="button"
                        >
                            {loggingOut
                                ? "Signing out…"
                                : "Sign out"}
                        </button>
                    </div>
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


function App() {
    const [user, setUser] =
        useState<CurrentUserResponse | null>(
            null,
        );
    const [checkingSession, setCheckingSession] =
        useState(true);
    const [sessionError, setSessionError] =
        useState<string | null>(null);
    const [sessionAttempt, setSessionAttempt] =
        useState(0);

    useEffect(() => {
        let cancelled = false;

        async function checkSession() {
            setCheckingSession(true);
            setSessionError(null);

            try {
                const currentUser =
                    await getCurrentUser();

                if (!cancelled) {
                    setUser(currentUser);
                }
            } catch (reason) {
                if (!cancelled) {
                    setSessionError(
                        reason instanceof Error
                            ? reason.message
                            : "Authentication check failed",
                    );
                }
            } finally {
                if (!cancelled) {
                    setCheckingSession(false);
                }
            }
        }

        void checkSession();

        return () => {
            cancelled = true;
        };
    }, [sessionAttempt]);

    async function handleLogin(
        username: string,
        password: string,
    ) {
        const authenticatedUser =
            await login(
                username,
                password,
            );

        setUser(authenticatedUser);
        setSessionError(null);
    }

    async function handleLogout() {
        await logout();
        setUser(null);
    }

    if (checkingSession) {
        return (
            <main className="app-shell centered-state">
                <div className="loading-card">
                    Checking session…
                </div>
            </main>
        );
    }

    if (sessionError && !user) {
        return (
            <main className="app-shell centered-state">
                <div className="error-card session-error-card">
                    <h1>Unable to check session</h1>
                    <p>{sessionError}</p>
                    <button
                        className="secondary-button"
                        onClick={() => {
                            setSessionAttempt(
                                (value) => value + 1,
                            );
                        }}
                        type="button"
                    >
                        Retry
                    </button>
                </div>
            </main>
        );
    }

    if (!user) {
        return (
            <LoginScreen
                onLogin={handleLogin}
            />
        );
    }

    return (
        <Dashboard
            onLogout={handleLogout}
            user={user}
        />
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
