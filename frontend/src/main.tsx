import React, {
    type FormEvent,
    useEffect,
    useMemo,
    useState,
} from "react";
import ReactDOM from "react-dom/client";

import {
    getAccountGames,
    getCurrentUser,
    getGame,
    getPlanetsAccounts,
    getScoreHistory,
    login,
    logout,
} from "./api/client";
import { PlayersTable } from "./features/players/PlayersTable";
import { MilitaryScoreChart } from "./features/statistics/MilitaryScoreChart";
import type {
    AccountGameSummary,
    CurrentUserResponse,
    GameDetailsResponse,
    PlanetsAccountResponse,
    ScoreHistoryResponse,
} from "./types/api";
import "./styles.css";

interface LoginScreenProps {
    onLogin: (username: string, password: string) => Promise<void>;
}

function LoginScreen({ onLogin }: LoginScreenProps) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSubmitting(true);
        setError(null);

        try {
            await onLogin(username.trim(), password);
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
                <div className="eyebrow">Planets.nu Intel</div>
                <h1>Sign in</h1>
                <p className="auth-subtitle">
                    Use your local Intel Client account.
                </p>
                <form className="auth-form" onSubmit={handleSubmit}>
                    <label>
                        <span>Username</span>
                        <input
                            autoComplete="username"
                            autoFocus
                            disabled={submitting}
                            name="username"
                            onChange={(event) => setUsername(event.target.value)}
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
                            onChange={(event) => setPassword(event.target.value)}
                            required
                            type="password"
                            value={password}
                        />
                    </label>
                    {error && (
                        <div className="auth-error" role="alert">
                            {error}
                        </div>
                    )}
                    <button
                        className="primary-button"
                        disabled={submitting || !username.trim() || !password}
                        type="submit"
                    >
                        {submitting ? "Signing in…" : "Sign in"}
                    </button>
                </form>
            </section>
        </main>
    );
}

function chooseGameId(
    games: AccountGameSummary[],
    previousGameId: number | null,
): number | null {
    if (
        previousGameId !== null &&
        games.some((game) => game.id === previousGameId)
    ) {
        return previousGameId;
    }

    const runningGame = games.find(
        (game) =>
            game.status_name.toLowerCase() === "running" ||
            game.status_id === 2,
    );

    return runningGame?.id ?? games[0]?.id ?? null;
}

interface DashboardProps {
    user: CurrentUserResponse;
    onLogout: () => Promise<void>;
}

function Dashboard({ user, onLogout }: DashboardProps) {
    const [accounts, setAccounts] = useState<PlanetsAccountResponse[]>([]);
    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [accountsLoading, setAccountsLoading] = useState(true);
    const [accountsError, setAccountsError] = useState<string | null>(null);

    const [games, setGames] = useState<AccountGameSummary[]>([]);
    const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
    const [gamesLoading, setGamesLoading] = useState(false);
    const [gamesError, setGamesError] = useState<string | null>(null);

    const [game, setGame] = useState<GameDetailsResponse | null>(null);
    const [history, setHistory] = useState<ScoreHistoryResponse | null>(null);
    const [dataLoading, setDataLoading] = useState(false);
    const [dataError, setDataError] = useState<string | null>(null);
    const [loggingOut, setLoggingOut] = useState(false);

    useEffect(() => {
        let cancelled = false;

        async function loadAccounts() {
            try {
                const response = await getPlanetsAccounts();
                if (cancelled) return;

                const activeAccounts = response.accounts.filter(
                    (account) => account.is_active,
                );
                setAccounts(activeAccounts);
                setSelectedAccountId(activeAccounts[0]?.id ?? null);
            } catch (reason) {
                if (!cancelled) {
                    setAccountsError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load linked accounts",
                    );
                }
            } finally {
                if (!cancelled) setAccountsLoading(false);
            }
        }

        void loadAccounts();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        let cancelled = false;

        if (selectedAccountId === null) {
            setGames([]);
            setSelectedGameId(null);
            setGamesError(null);
            setGamesLoading(false);
            return () => {
                cancelled = true;
            };
        }

        const accountId = selectedAccountId;

        async function loadGames() {
            setGamesLoading(true);
            setGamesError(null);
            setGames([]);

            try {
                const response = await getAccountGames(accountId);
                if (cancelled) return;

                setGames(response.games);
                setSelectedGameId((previous) =>
                    chooseGameId(response.games, previous),
                );
            } catch (reason) {
                if (!cancelled) {
                    setGamesError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load games",
                    );
                }
            } finally {
                if (!cancelled) setGamesLoading(false);
            }
        }

        void loadGames();
        return () => {
            cancelled = true;
        };
    }, [selectedAccountId]);

    useEffect(() => {
        let cancelled = false;

        if (selectedGameId === null) {
            setGame(null);
            setHistory(null);
            setDataError(null);
            setDataLoading(false);
            return () => {
                cancelled = true;
            };
        }

        const gameId = selectedGameId;

        async function loadGameData() {
            setDataLoading(true);
            setDataError(null);
            setGame(null);
            setHistory(null);

            try {
                const [gameResponse, historyResponse] = await Promise.all([
                    getGame(gameId),
                    getScoreHistory(gameId),
                ]);
                if (cancelled) return;

                setGame(gameResponse);
                setHistory(historyResponse);
            } catch (reason) {
                if (!cancelled) {
                    setDataError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load game data",
                    );
                }
            } finally {
                if (!cancelled) setDataLoading(false);
            }
        }

        void loadGameData();
        return () => {
            cancelled = true;
        };
    }, [selectedGameId]);

    const latestScores = useMemo(() => {
        const result = new Map<number, ScoreHistoryResponse["items"][number]>();
        if (!history) return result;

        for (const item of history.items) {
            const current = result.get(item.slot_id);
            if (!current || item.turn > current.turn) {
                result.set(item.slot_id, item);
            }
        }
        return result;
    }, [history]);

    const selectedAccount =
        accounts.find((account) => account.id === selectedAccountId) ?? null;
    const selectedGame =
        games.find((item) => item.id === selectedGameId) ?? null;

    async function handleLogout() {
        setLoggingOut(true);
        try {
            await onLogout();
        } finally {
            setLoggingOut(false);
        }
    }

    if (accountsLoading) {
        return (
            <main className="app-shell centered-state">
                <div className="loading-card">Loading linked Planets.nu accounts…</div>
            </main>
        );
    }

    if (accountsError || accounts.length === 0) {
        return (
            <main className="app-shell centered-state">
                <div className="error-card">
                    <h1>{accountsError ? "Failed to load observers" : "No active observers"}</h1>
                    <p>
                        {accountsError ??
                            "No active linked Planets.nu accounts are available."}
                    </p>
                </div>
            </main>
        );
    }

    return (
        <main className="app-shell">
            <header className="topbar">
                <div>
                    <div className="eyebrow">Planets.nu Intel</div>
                    <h1>{game?.game.name ?? selectedGame?.name ?? "Dashboard"}</h1>
                    <p className="subtitle">
                        {game?.game.short_description ??
                            selectedGame?.short_description ??
                            "Select an observer and game."}
                    </p>
                </div>
                <div className="topbar-actions">
                    {game && (
                        <div className="game-status">
                            <span className="status-badge">{game.game.status_name}</span>
                            <strong>Turn {game.game.turn}</strong>
                            <span>{game.game.slots} slots</span>
                        </div>
                    )}
                    <div className="user-menu">
                        <div>
                            <span className="user-label">Signed in as</span>
                            <strong>{user.display_name}</strong>
                        </div>
                        <button
                            className="secondary-button"
                            disabled={loggingOut}
                            onClick={() => void handleLogout()}
                            type="button"
                        >
                            {loggingOut ? "Signing out…" : "Sign out"}
                        </button>
                    </div>
                </div>
            </header>

            <section className="summary-grid">
                <label className="summary-card">
                    <span>Observer</span>
                    <select
                        className="secondary-button"
                        onChange={(event) =>
                            setSelectedAccountId(Number(event.target.value))
                        }
                        value={selectedAccountId ?? ""}
                    >
                        {accounts.map((account) => (
                            <option key={account.id} value={account.id}>
                                {account.planets_username}
                            </option>
                        ))}
                    </select>
                </label>

                <label className="summary-card">
                    <span>Game</span>
                    <select
                        className="secondary-button"
                        disabled={gamesLoading || games.length === 0}
                        onChange={(event) =>
                            setSelectedGameId(Number(event.target.value))
                        }
                        value={selectedGameId ?? ""}
                    >
                        {gamesLoading ? (
                            <option value="">Loading games…</option>
                        ) : games.length === 0 ? (
                            <option value="">No games available</option>
                        ) : (
                            games.map((item) => (
                                <option key={item.id} value={item.id}>
                                    {item.name} · Turn {item.turn} · {item.status_name}
                                </option>
                            ))
                        )}
                    </select>
                </label>
            </section>

            {selectedAccount && (
                <div className="eyebrow">
                    Observer provenance: {selectedAccount.planets_username}
                </div>
            )}

            {gamesLoading ? (
                <div className="loading-card">Loading games for observer…</div>
            ) : gamesError ? (
                <div className="error-card">
                    <h1>Failed to load games</h1>
                    <p>{gamesError}</p>
                </div>
            ) : games.length === 0 ? (
                <div className="error-card">
                    <h1>No games available</h1>
                    <p>This observer has no available Planets.nu games.</p>
                </div>
            ) : dataLoading ? (
                <div className="loading-card">Loading game intelligence…</div>
            ) : dataError || !game || !history ? (
                <div className="error-card">
                    <h1>Failed to load game</h1>
                    <p>{dataError ?? "Game data is unavailable."}</p>
                </div>
            ) : (
                <>
                    <section className="summary-grid">
                        <div className="summary-card">
                            <span>Planets</span>
                            <strong>{game.settings.num_planets}</strong>
                        </div>
                        <div className="summary-card">
                            <span>Ship limit</span>
                            <strong>{game.settings.ship_limit}</strong>
                        </div>
                        <div className="summary-card">
                            <span>Schedule</span>
                            <strong>{game.schedule}</strong>
                        </div>
                        <div className="summary-card">
                            <span>Next host</span>
                            <strong>{game.time_to_host}</strong>
                        </div>
                    </section>
                    <PlayersTable players={game.players} latestScores={latestScores} />
                    <MilitaryScoreChart players={game.players} history={history.items} />
                </>
            )}
        </main>
    );
}

function App() {
    const [user, setUser] = useState<CurrentUserResponse | null>(null);
    const [checkingSession, setCheckingSession] = useState(true);
    const [sessionError, setSessionError] = useState<string | null>(null);
    const [sessionAttempt, setSessionAttempt] = useState(0);

    useEffect(() => {
        let cancelled = false;

        async function checkSession() {
            setCheckingSession(true);
            setSessionError(null);
            try {
                const currentUser = await getCurrentUser();
                if (!cancelled) setUser(currentUser);
            } catch (reason) {
                if (!cancelled) {
                    setSessionError(
                        reason instanceof Error
                            ? reason.message
                            : "Authentication check failed",
                    );
                }
            } finally {
                if (!cancelled) setCheckingSession(false);
            }
        }

        void checkSession();
        return () => {
            cancelled = true;
        };
    }, [sessionAttempt]);

    async function handleLogin(username: string, password: string) {
        const authenticatedUser = await login(username, password);
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
                <div className="loading-card">Checking session…</div>
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
                        onClick={() => setSessionAttempt((value) => value + 1)}
                        type="button"
                    >
                        Retry
                    </button>
                </div>
            </main>
        );
    }

    if (!user) return <LoginScreen onLogin={handleLogin} />;

    return <Dashboard onLogout={handleLogout} user={user} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
);
