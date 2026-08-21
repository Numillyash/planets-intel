import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import {
    getAccountGames,
    getGame,
    getLatestPrivateIntel,
    getPlanetsAccounts,
    getScoreHistory,
    refreshAccessiblePrivateIntel,
} from "../../api/client";
import {
    readRememberedObserverId,
    rememberObserverId,
} from "../../lib/observerSelection";
import type {
    AccountGameSummary,
    CurrentUserResponse,
    GameDetailsResponse,
    LatestPrivateIntelResponse,
    PlanetsAccountResponse,
    ScoreHistoryResponse,
} from "../../types/api";
import { PrivateIntelMap } from "../map/PrivateIntelMap";
import { GameDashboard } from "./GameDashboard";

interface IntelboardRoute {
    observer: string | null;
    gameId: number | null;
}

const AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

function parseIntelboardRoute(pathname: string): IntelboardRoute {
    const match = pathname.match(/^\/intelboard\/([^/]+)\/(\d+)\/?$/i);
    if (match === null) {
        return { observer: null, gameId: null };
    }

    const gameId = Number(match[2]);
    if (!Number.isSafeInteger(gameId) || gameId <= 0) {
        return { observer: null, gameId: null };
    }

    try {
        return {
            observer: decodeURIComponent(match[1]),
            gameId,
        };
    } catch {
        return { observer: match[1], gameId };
    }
}

function intelboardPath(observer: string, gameId: number): string {
    return `/intelboard/${encodeURIComponent(observer)}/${gameId}`;
}

function sameObserver(left: string | null, right: string): boolean {
    return left !== null && left.localeCompare(right, undefined, {
        sensitivity: "accent",
    }) === 0;
}

function chooseGameId(
    games: AccountGameSummary[],
    preferredGameId: number | null,
): number | null {
    if (
        preferredGameId !== null &&
        games.some((game) => game.id === preferredGameId)
    ) {
        return preferredGameId;
    }

    const runningGame = games.find(
        (game) =>
            game.status_name.toLowerCase() === "running" ||
            game.status_id === 2,
    );

    return runningGame?.id ?? games[0]?.id ?? null;
}

export function DashboardApp({
    user,
    onLogout,
}: {
    user: CurrentUserResponse;
    onLogout: () => Promise<void>;
}) {
    const [initialRoute] = useState<IntelboardRoute>(() =>
        parseIntelboardRoute(window.location.pathname),
    );

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

    const [privateIntel, setPrivateIntel] =
        useState<LatestPrivateIntelResponse | null>(null);
    const [privateIntelLoading, setPrivateIntelLoading] = useState(false);
    const [privateIntelError, setPrivateIntelError] = useState<string | null>(null);

    const [loggingOut, setLoggingOut] = useState(false);
    const refreshInFlightRef = useRef(false);

    useEffect(() => {
        let cancelled = false;

        async function loadAccounts() {
            setAccountsLoading(true);
            setAccountsError(null);
            try {
                const response = await getPlanetsAccounts();
                if (cancelled) return;

                const activeAccounts = response.accounts.filter(
                    (account) => account.is_active,
                );
                setAccounts(activeAccounts);
                setSelectedAccountId((previous) => {
                    const routed = activeAccounts.find((account) =>
                        sameObserver(
                            initialRoute.observer,
                            account.planets_username,
                        ),
                    );
                    if (routed !== undefined) return routed.id;

                    if (
                        previous !== null &&
                        activeAccounts.some((account) => account.id === previous)
                    ) {
                        return previous;
                    }

                    const rememberedId = readRememberedObserverId();
                    if (
                        rememberedId !== null &&
                        activeAccounts.some((account) => account.id === rememberedId)
                    ) {
                        return rememberedId;
                    }

                    return activeAccounts[0]?.id ?? null;
                });
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
    }, [initialRoute.observer]);

    useEffect(() => {
        rememberObserverId(selectedAccountId);
    }, [selectedAccountId]);

    useEffect(() => {
        let cancelled = false;

        if (selectedAccountId === null) {
            setGames([]);
            setSelectedGameId(null);
            setGamesError(null);
            setGamesLoading(false);
            return () => { cancelled = true; };
        }

        const accountId = selectedAccountId;
        const selectedAccount = accounts.find(
            (account) => account.id === accountId,
        ) ?? null;

        async function loadGames() {
            setGamesLoading(true);
            setGamesError(null);
            setGames([]);

            try {
                const response = await getAccountGames(accountId);
                if (cancelled) return;
                setGames(response.games);

                const routedGameId =
                    selectedAccount !== null &&
                    sameObserver(
                        initialRoute.observer,
                        selectedAccount.planets_username,
                    )
                        ? initialRoute.gameId
                        : null;

                setSelectedGameId((previous) =>
                    chooseGameId(
                        response.games,
                        routedGameId ?? previous,
                    ),
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
        return () => { cancelled = true; };
    }, [accounts, initialRoute.gameId, initialRoute.observer, selectedAccountId]);

    useEffect(() => {
        let cancelled = false;

        if (selectedGameId === null) {
            setGame(null);
            setHistory(null);
            setDataError(null);
            setDataLoading(false);
            return () => { cancelled = true; };
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
        return () => { cancelled = true; };
    }, [selectedGameId]);

    const selectedAccount =
        accounts.find((account) => account.id === selectedAccountId) ?? null;
    const selectedGame =
        games.find((item) => item.id === selectedGameId) ?? null;

    useEffect(() => {
        if (selectedAccount === null || selectedGame === null) return;

        const desiredPath = intelboardPath(
            selectedAccount.planets_username,
            selectedGame.id,
        );
        if (window.location.pathname !== desiredPath) {
            window.history.replaceState(
                null,
                "",
                `${desiredPath}${window.location.search}${window.location.hash}`,
            );
        }
    }, [selectedAccount, selectedGame]);

    useEffect(() => {
        let cancelled = false;

        if (
            selectedAccountId === null ||
            selectedGameId === null
        ) {
            setPrivateIntel(null);
            setPrivateIntelError(null);
            setPrivateIntelLoading(false);
            return () => { cancelled = true; };
        }

        const accountId = selectedAccountId;
        const gameId = selectedGameId;

        async function loadPrivateIntel() {
            setPrivateIntelLoading(true);
            setPrivateIntelError(null);
            setPrivateIntel(null);

            try {
                const response = await getLatestPrivateIntel(gameId, accountId);
                if (!cancelled) setPrivateIntel(response);
            } catch (reason) {
                if (!cancelled) {
                    setPrivateIntelError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load private intelligence",
                    );
                }
            } finally {
                if (!cancelled) setPrivateIntelLoading(false);
            }
        }

        void loadPrivateIntel();
        return () => { cancelled = true; };
    }, [selectedAccountId, selectedGameId]);

    const refreshDashboardData = useCallback(async () => {
        if (
            selectedAccountId === null ||
            selectedGameId === null ||
            refreshInFlightRef.current
        ) {
            return;
        }

        const accountId = selectedAccountId;
        const gameId = selectedGameId;
        refreshInFlightRef.current = true;
        setPrivateIntelLoading(true);
        setPrivateIntelError(null);

        try {
            await refreshAccessiblePrivateIntel(gameId);
            const [intelResponse, historyResponse, gameResponse] = await Promise.all([
                getLatestPrivateIntel(gameId, accountId),
                getScoreHistory(gameId),
                getGame(gameId),
            ]);
            setPrivateIntel(intelResponse);
            setHistory(historyResponse);
            setGame(gameResponse);
        } catch (reason) {
            setPrivateIntelError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to refresh dashboard intelligence",
            );
        } finally {
            refreshInFlightRef.current = false;
            setPrivateIntelLoading(false);
        }
    }, [selectedAccountId, selectedGameId]);

    useEffect(() => {
        if (
            selectedAccountId === null ||
            selectedGameId === null ||
            selectedGame === null
        ) {
            return;
        }

        const isRunning =
            selectedGame.status_name.toLowerCase() === "running" ||
            selectedGame.status_id === 2;
        if (!isRunning) return;

        void refreshDashboardData();
        const intervalId = window.setInterval(
            () => void refreshDashboardData(),
            AUTO_REFRESH_INTERVAL_MS,
        );
        return () => window.clearInterval(intervalId);
    }, [
        refreshDashboardData,
        selectedAccountId,
        selectedGame,
        selectedGameId,
    ]);

    const latestScores = useMemo(() => {
        const result = new Map<number, ScoreHistoryResponse["items"][number]>();
        if (history === null) return result;

        for (const item of history.items) {
            const current = result.get(item.slot_id);
            if (!current || item.turn > current.turn) {
                result.set(item.slot_id, item);
            }
        }
        return result;
    }, [history]);

    async function handlePrivateIntelRefresh() {
        await refreshDashboardData();
    }

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

    if (accountsError) {
        return (
            <main className="app-shell centered-state">
                <div className="error-card">
                    <h1>Failed to load observers</h1>
                    <p>{accountsError}</p>
                </div>
            </main>
        );
    }

    if (accounts.length === 0) {
        return (
            <main className="app-shell centered-state">
                <div className="error-card">
                    <h1>No active observers</h1>
                    <p>Manage linked Planets.nu accounts from the shared Games home.</p>
                    <button
                        className="secondary-button"
                        onClick={() => window.location.assign("/intelboard")}
                        type="button"
                    >
                        Open Games
                    </button>
                </div>
            </main>
        );
    }

    return (
        <main className="app-shell">
            <header className="topbar">
                <div>
                    <div className="eyebrow">Planets.nu Intel</div>
                    <h1>{game?.game.name ?? selectedGame?.name ?? "Game dashboard"}</h1>
                    <p className="subtitle">
                        {game?.game.short_description
                            ?? selectedGame?.short_description
                            ?? "Select an observer and game."}
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
                        onChange={(event) => {
                            setSelectedGameId(null);
                            setSelectedAccountId(Number(event.target.value));
                        }}
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
            ) : dataError || game === null || selectedAccount === null ? (
                <div className="error-card">
                    <h1>Failed to load game</h1>
                    <p>{dataError ?? "Game data is unavailable."}</p>
                </div>
            ) : (
                <>
                    <GameDashboard
                        game={game}
                        history={history}
                        latestScores={latestScores}
                        onRefresh={() => void handlePrivateIntelRefresh()}
                        privateIntel={privateIntel}
                        refreshing={privateIntelLoading}
                        selectedAccount={selectedAccount}
                    />

                    <PrivateIntelMap
                        error={privateIntelError}
                        intel={privateIntel}
                        loading={privateIntelLoading}
                        observerName={selectedAccount.planets_username}
                        players={game.players}
                    />
                </>
            )}
        </main>
    );
}
