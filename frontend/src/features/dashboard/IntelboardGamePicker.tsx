import { useEffect, useMemo, useState } from "react";

import {
    getAccountGames,
    getGame,
    getPlanetsAccounts,
} from "../../api/client";
import {
    readRememberedObserverId,
    rememberObserverId,
} from "../../lib/observerSelection";
import type {
    AccountGameSummary,
    CurrentUserResponse,
    GameDetailsResponse,
    PlanetsAccountResponse,
    PlayerInfo,
} from "../../types/api";
import "./intelboard-game-picker.css";

interface IntelboardGamePickerProps {
    user: CurrentUserResponse;
    onLogout: () => Promise<void>;
}

function gamePath(observer: string, gameId: number): string {
    return `/intelboard/${encodeURIComponent(observer)}/${gameId}`;
}

function pickerPath(observer: string): string {
    return `/intelboard/${encodeURIComponent(observer)}`;
}

function routedObserver(pathname: string): string | null {
    const match = pathname.match(/^\/intelboard\/([^/]+)\/?$/i);
    if (match === null) return null;
    try {
        return decodeURIComponent(match[1]);
    } catch {
        return match[1];
    }
}

function sameObserver(left: string | null, right: string): boolean {
    return left !== null && left.localeCompare(right, undefined, {
        sensitivity: "accent",
    }) === 0;
}

function isRunning(game: AccountGameSummary): boolean {
    return game.status_id === 2 || game.status_name.toLowerCase() === "running";
}

function observerPlayer(
    details: GameDetailsResponse | undefined,
    account: PlanetsAccountResponse | null,
): PlayerInfo | null {
    if (details === undefined || account === null) return null;

    if (account.planets_account_id !== null) {
        const byId = details.players.find(
            (player) => player.account_id === account.planets_account_id,
        );
        if (byId !== undefined) return byId;
    }

    const username = account.planets_username.trim().toLocaleLowerCase();
    return details.players.find(
        (player) => player.username.trim().toLocaleLowerCase() === username,
    ) ?? null;
}

function GameCard({
    game,
    details,
    account,
}: {
    game: AccountGameSummary;
    details: GameDetailsResponse | undefined;
    account: PlanetsAccountResponse;
}) {
    const player = observerPlayer(details, account);
    const running = isRunning(game);

    return (
        <button
            className="intelboard-game-card"
            onClick={() => {
                rememberObserverId(account.id);
                window.location.assign(
                    gamePath(account.planets_username, game.id),
                );
            }}
            type="button"
        >
            <div className="intelboard-game-card-heading">
                <div>
                    <span className="intelboard-game-id">GAME #{game.id}</span>
                    <h2>{game.name}</h2>
                </div>
                <span
                    className={
                        "intelboard-game-status"
                        + (running ? " is-running" : "")
                    }
                >
                    {game.status_name}
                </span>
            </div>

            {game.short_description && (
                <p className="intelboard-game-description">
                    {game.short_description}
                </p>
            )}

            <div className="intelboard-game-meta">
                <div>
                    <span>Turn</span>
                    <strong>{game.turn}</strong>
                </div>
                <div>
                    <span>Players</span>
                    <strong>{game.slots}</strong>
                </div>
                <div>
                    <span>Next host</span>
                    <strong>{game.time_to_host || "—"}</strong>
                </div>
                <div>
                    <span>Type</span>
                    <strong>
                        {game.is_custom
                            ? "Custom"
                            : game.is_private
                                ? "Private"
                                : "Standard"}
                    </strong>
                </div>
            </div>

            {player !== null && (
                <div className="intelboard-player-strip">
                    <span>
                        <strong>{player.planets}</strong>
                        planets
                    </span>
                    <span>
                        <strong>{player.ships}</strong>
                        ships
                    </span>
                    <span>
                        <strong>{player.starbases}</strong>
                        bases
                    </span>
                    <span className={player.turn_ready ? "is-ready" : ""}>
                        {player.turn_ready ? "Turn ready" : "Turn open"}
                    </span>
                </div>
            )}

            <div className="intelboard-game-open">
                Open game
                <span aria-hidden="true">→</span>
            </div>
        </button>
    );
}

export function IntelboardGamePicker({
    user,
    onLogout,
}: IntelboardGamePickerProps) {
    const [accounts, setAccounts] = useState<PlanetsAccountResponse[]>([]);
    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [games, setGames] = useState<AccountGameSummary[]>([]);
    const [detailsByGameId, setDetailsByGameId] =
        useState<Map<number, GameDetailsResponse>>(new Map());
    const [loadingAccounts, setLoadingAccounts] = useState(true);
    const [loadingGames, setLoadingGames] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loggingOut, setLoggingOut] = useState(false);

    useEffect(() => {
        let cancelled = false;

        async function loadAccounts() {
            setLoadingAccounts(true);
            setError(null);
            try {
                const response = await getPlanetsAccounts();
                if (cancelled) return;
                const active = response.accounts.filter((account) => account.is_active);
                const routeObserver = routedObserver(window.location.pathname);
                const routed = active.find((account) =>
                    sameObserver(routeObserver, account.planets_username),
                ) ?? null;
                const rememberedId = readRememberedObserverId();
                const remembered = rememberedId === null
                    ? null
                    : active.find((account) => account.id === rememberedId) ?? null;
                const selected = routed ?? remembered ?? active[0] ?? null;
                setAccounts(active);
                setSelectedAccountId(selected?.id ?? null);
                if (selected !== null) rememberObserverId(selected.id);
            } catch (reason) {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load linked Planets.nu accounts",
                    );
                }
            } finally {
                if (!cancelled) setLoadingAccounts(false);
            }
        }

        void loadAccounts();
        return () => {
            cancelled = true;
        };
    }, []);

    const selectedAccount = accounts.find(
        (account) => account.id === selectedAccountId,
    ) ?? null;

    useEffect(() => {
        if (selectedAccount === null) return;
        rememberObserverId(selectedAccount.id);
        const desiredPath = pickerPath(selectedAccount.planets_username);
        if (window.location.pathname !== desiredPath) {
            window.history.replaceState(
                null,
                "",
                `${desiredPath}${window.location.search}${window.location.hash}`,
            );
        }
    }, [selectedAccount]);

    useEffect(() => {
        let cancelled = false;

        if (selectedAccountId === null) {
            setGames([]);
            setDetailsByGameId(new Map());
            return () => {
                cancelled = true;
            };
        }

        rememberObserverId(selectedAccountId);
        const accountId = selectedAccountId;

        async function loadGames() {
            setLoadingGames(true);
            setError(null);
            setGames([]);
            setDetailsByGameId(new Map());

            try {
                const response = await getAccountGames(accountId);
                if (cancelled) return;
                setGames(response.games);

                const details = await Promise.allSettled(
                    response.games.map((game) => getGame(game.id)),
                );
                if (cancelled) return;

                const next = new Map<number, GameDetailsResponse>();
                details.forEach((result, index) => {
                    if (result.status === "fulfilled") {
                        next.set(response.games[index].id, result.value);
                    }
                });
                setDetailsByGameId(next);
            } catch (reason) {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load games",
                    );
                }
            } finally {
                if (!cancelled) setLoadingGames(false);
            }
        }

        void loadGames();
        return () => {
            cancelled = true;
        };
    }, [selectedAccountId]);

    const sortedGames = useMemo(() => {
        return [...games].sort((left, right) => {
            const runningDifference = Number(isRunning(right)) - Number(isRunning(left));
            if (runningDifference !== 0) return runningDifference;
            if (right.turn !== left.turn) return right.turn - left.turn;
            return left.name.localeCompare(right.name);
        });
    }, [games]);

    async function handleLogout() {
        setLoggingOut(true);
        try {
            await onLogout();
        } finally {
            setLoggingOut(false);
        }
    }

    return (
        <main className="intelboard-game-menu">
            <header className="intelboard-game-menu-header">
                <div>
                    <div className="eyebrow">PLANETS.NU INTEL</div>
                    <h1>Choose a game</h1>
                    <p>
                        Open an operational dashboard or return here from the starmap.
                    </p>
                </div>

                <div className="intelboard-game-menu-user">
                    <div>
                        <span>Signed in as</span>
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
            </header>

            <section className="intelboard-game-menu-toolbar">
                <label>
                    <span>Observer</span>
                    <select
                        className="secondary-button"
                        disabled={loadingAccounts || accounts.length === 0}
                        onChange={(event) => {
                            const accountId = Number(event.target.value);
                            rememberObserverId(accountId);
                            setSelectedAccountId(accountId);
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

                {selectedAccount !== null && (
                    <div className="intelboard-observer-summary">
                        <span>Planets.nu observer</span>
                        <strong>{selectedAccount.planets_username}</strong>
                    </div>
                )}
            </section>

            {loadingAccounts || loadingGames ? (
                <div className="intelboard-game-menu-state">
                    Loading games…
                </div>
            ) : error !== null ? (
                <div className="intelboard-game-menu-state is-error">
                    {error}
                </div>
            ) : accounts.length === 0 ? (
                <div className="intelboard-game-menu-state">
                    No active Planets.nu observers are linked.
                </div>
            ) : sortedGames.length === 0 ? (
                <div className="intelboard-game-menu-state">
                    No games are available for this observer.
                </div>
            ) : (
                <section className="intelboard-game-grid">
                    {sortedGames.map((game) => (
                        <GameCard
                            account={selectedAccount!}
                            details={detailsByGameId.get(game.id)}
                            game={game}
                            key={game.id}
                        />
                    ))}
                </section>
            )}
        </main>
    );
}