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
import { raceName } from "../../lib/races";
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

const GAME_PICKER_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

type PlayerTurnState =
    | "ready"
    | "viewed"
    | "unopened"
    | "unknown"
    | "inactive"
    | "computer"
    | "empty";

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

function gameStatusRank(game: AccountGameSummary): number {
    if (isRunning(game)) return 0;
    const normalized = game.status_name.trim().toLowerCase();
    if (normalized === "joining") return 1;
    if (normalized === "finished") return 3;
    return 2;
}

function sortedGames(games: AccountGameSummary[]): AccountGameSummary[] {
    return [...games].sort((left, right) => {
        const statusDifference = gameStatusRank(left) - gameStatusRank(right);
        if (statusDifference !== 0) return statusDifference;
        if (right.turn !== left.turn) return right.turn - left.turn;
        return left.name.localeCompare(right.name);
    });
}

function observerPlayer(
    details: GameDetailsResponse | undefined,
    account: PlanetsAccountResponse,
): PlayerInfo | null {
    if (details === undefined) return null;

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

function loadInfoTurnState(player: PlayerInfo): PlayerTurnState {
    if (player.race_id >= 100) return "computer";
    if (player.status !== 1) return "inactive";
    if (player.turn_ready === true) return "ready";
    if (player.turn_status !== null && player.turn_status > 0) return "viewed";
    if (player.turn_status === 0) return "unopened";
    return "unknown";
}

function officialTurnMarkerState(marker: string | undefined): PlayerTurnState | null {
    if (marker === undefined || marker === "") return null;
    const normalized = marker.toLowerCase();
    if (marker === "_") return "unopened";
    if (normalized === "o") return "viewed";
    if (normalized === "x") return "inactive";
    if (normalized === "c") return "computer";

    // Planets.nu games/list encodes a completed turn with a race marker.
    // Treat every remaining non-whitespace marker as DONE instead of trying to
    // reinterpret the race encoding locally (important for races 10+).
    return marker.trim() === "" ? null : "ready";
}

function compactTurnStates(
    accountTurnStatus: string | null,
    loadInfoTurnStatus: string | null,
    slot: number,
    loadInfoMatchesTurn: boolean,
): PlayerTurnState[] {
    const states: PlayerTurnState[] = [];
    const account = officialTurnMarkerState(accountTurnStatus?.[slot - 1]);
    if (account !== null) states.push(account);

    if (loadInfoMatchesTurn) {
        const loadInfo = officialTurnMarkerState(loadInfoTurnStatus?.[slot - 1]);
        if (loadInfo !== null) states.push(loadInfo);
    }
    return states;
}

function gameTurnState(
    accountTurnStatus: string | null,
    loadInfoTurnStatus: string | null,
    slot: number,
    player: PlayerInfo | null,
    loadInfoMatchesTurn: boolean,
): PlayerTurnState {
    const compactStates = compactTurnStates(
        accountTurnStatus,
        loadInfoTurnStatus,
        slot,
        loadInfoMatchesTurn,
    );

    // Structural states are monotonic inside one game turn. Once either public
    // game object reports a slot dead/inactive or computer, stale progress
    // metadata from another endpoint must not resurrect it.
    if (compactStates.includes("inactive")) return "inactive";
    if (compactStates.includes("computer")) return "computer";

    if (player === null) {
        if (compactStates.includes("ready")) return "ready";
        if (compactStates.includes("viewed")) return "viewed";
        if (compactStates.includes("unopened")) return "unopened";
        return "empty";
    }

    if (loadInfoMatchesTurn) {
        if (player.race_id >= 100) return "computer";
        if (player.status !== 1) return "inactive";
    }

    const loadInfo = loadInfoMatchesTurn
        ? loadInfoTurnState(player)
        : "unknown";

    // Opening/submitting a turn is monotonic within one turn. games/list, the
    // loadinfo game object, and loadinfo.players[] can be refreshed at slightly
    // different moments, so the most advanced compatible factual state wins.
    // This is especially important when one compact rail still says '_' while
    // another public source already reports VIEWED.
    if (compactStates.includes("ready") || loadInfo === "ready") return "ready";
    if (compactStates.includes("viewed") || loadInfo === "viewed") return "viewed";
    if (compactStates.includes("unopened") || loadInfo === "unopened") return "unopened";

    return "unknown";
}

function turnStateLabel(state: PlayerTurnState): string {
    switch (state) {
        case "ready": return "turn complete";
        case "viewed": return "viewed / incomplete";
        case "unopened": return "not viewed";
        case "computer": return "computer player";
        case "inactive": return "inactive / dead";
        case "empty": return "empty slot / status unknown";
        default: return "turn status unknown";
    }
}

function missedTurnClass(
    player: PlayerInfo,
    state: PlayerTurnState,
    loadInfoMatchesTurn: boolean,
): string {
    if (
        !loadInfoMatchesTurn
        || player.status !== 1
        || player.race_id >= 100
        || player.turns_missed === null
        || player.turns_missed <= 0
    ) {
        return "";
    }

    if (player.turns_missed >= 3) return " is-missed-critical";
    if (player.turns_missed === 2 && state !== "ready") {
        return " is-missed-critical-risk";
    }
    if (player.turns_missed === 2) return " is-missed-warning";
    return " is-missed-watch";
}

function missedTurnLabel(
    player: PlayerInfo,
    state: PlayerTurnState,
    loadInfoMatchesTurn: boolean,
): string {
    if (
        !loadInfoMatchesTurn
        || player.status !== 1
        || player.race_id >= 100
        || player.turns_missed === null
        || player.turns_missed <= 0
    ) {
        return "";
    }

    const turns = player.turns_missed;
    const base = `${turns} consecutive missed turn${turns === 1 ? "" : "s"} reported by Planets.nu`;
    if (turns === 2 && state !== "ready") {
        return `${base} · current turn incomplete · critical drop risk if another turn is missed`;
    }
    return base;
}

function PlayerTurnRail({
    details,
    gameTurn,
    slots,
    turnStatus,
}: {
    details: GameDetailsResponse | undefined;
    gameTurn: number;
    slots: number;
    turnStatus: string | null;
}) {
    const bySlot = new Map<number, PlayerInfo>();
    for (const player of details?.players ?? []) {
        if (player.slot_id > 0) bySlot.set(player.slot_id, player);
    }

    const loadInfoMatchesTurn = details?.game.turn === gameTurn;
    const loadInfoTurnStatus = loadInfoMatchesTurn
        ? details?.game.turn_status ?? null
        : null;
    const slotCount = Math.max(
        slots,
        turnStatus?.length ?? 0,
        loadInfoTurnStatus?.length ?? 0,
        ...Array.from(bySlot.keys()),
        0,
    );
    if (slotCount <= 0) return null;

    const densityClass = slotCount > 20
        ? " is-very-dense"
        : slotCount > 14
            ? " is-dense"
            : "";

    return (
        <div
            aria-label={`Turn status for ${slotCount} player slots`}
            className={`intelboard-turn-rail${densityClass}`}
        >
            {Array.from({ length: slotCount }, (_, index) => {
                const slot = index + 1;
                const player = bySlot.get(slot) ?? null;
                const state = gameTurnState(
                    turnStatus,
                    loadInfoTurnStatus,
                    slot,
                    player,
                    loadInfoMatchesTurn,
                );

                if (player === null) {
                    return (
                        <span
                            className={`intelboard-turn-cell is-${state}`}
                            key={slot}
                            title={`Slot ${slot} · no public player record · ${turnStateLabel(state)}`}
                        >
                            {slot}
                        </span>
                    );
                }

                const username = player.username.trim() || "computer";
                const missedClass = missedTurnClass(
                    player,
                    state,
                    loadInfoMatchesTurn,
                );
                const missedLabel = missedTurnLabel(
                    player,
                    state,
                    loadInfoMatchesTurn,
                );
                return (
                    <span
                        className={`intelboard-turn-cell is-${state}${missedClass}`}
                        key={slot}
                        title={
                            `${raceName(player.race_id)} / slot ${slot} / ${username} · ${turnStateLabel(state)}`
                            + (missedLabel ? ` · ${missedLabel}` : "")
                        }
                    >
                        {slot}
                    </span>
                );
            })}
        </div>
    );
}

function GameRow({
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
    const loadInfoMatchesTurn = details?.game.turn === game.turn;
    const loadInfoTurnStatus = loadInfoMatchesTurn
        ? details?.game.turn_status ?? null
        : null;
    const ownState = !running || player === null
        ? null
        : gameTurnState(
            game.turn_status,
            loadInfoTurnStatus,
            player.slot_id,
            player,
            loadInfoMatchesTurn,
        );
    const typeLabel = game.is_custom
        ? "Custom"
        : game.is_private
            ? "Private"
            : "Standard";

    return (
        <button
            className="intelboard-game-row"
            onClick={() => {
                rememberObserverId(account.id);
                window.location.assign(
                    gamePath(account.planets_username, game.id),
                );
            }}
            type="button"
        >
            <div className="intelboard-game-row-main">
                <div className="intelboard-game-row-title">
                    <span className="intelboard-game-id">GAME #{game.id}</span>
                    <h2>{game.name}</h2>
                    <p>{game.short_description || typeLabel}</p>
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

            <div className="intelboard-game-row-meta">
                <span><strong>T{game.turn}</strong> turn</span>
                <span><strong>{game.slots}</strong> slots</span>
                <span><strong>{typeLabel}</strong></span>
                <span className="intelboard-next-host">{game.time_to_host || "Host time unknown"}</span>
            </div>

            {player !== null && (
                <div className="intelboard-observer-game-summary">
                    <span><strong>{player.planets ?? "—"}</strong> planets</span>
                    <span><strong>{player.ships ?? "—"}</strong> ships</span>
                    <span><strong>{player.starbases ?? "—"}</strong> bases</span>
                    {ownState !== null && (
                        <span className={`intelboard-own-turn-state is-${ownState}`}>
                            <i aria-hidden="true" />
                            {turnStateLabel(ownState)}
                        </span>
                    )}
                </div>
            )}

            {running && (
                <PlayerTurnRail
                    details={details}
                    gameTurn={game.turn}
                    slots={game.slots}
                    turnStatus={game.turn_status}
                />
            )}
        </button>
    );
}

function accountInitials(username: string): string {
    const words = username.trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return "?";
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toUpperCase();
}

function AccountColumn({
    account,
    games,
    detailsByGameId,
    error,
    selected,
    onSelect,
}: {
    account: PlanetsAccountResponse;
    games: AccountGameSummary[];
    detailsByGameId: Map<number, GameDetailsResponse>;
    error: string | null;
    selected: boolean;
    onSelect: () => void;
}) {
    const orderedGames = useMemo(() => sortedGames(games), [games]);
    const [profileImageFailed, setProfileImageFailed] = useState(false);

    useEffect(() => {
        setProfileImageFailed(false);
    }, [account.profile_image_url]);

    const showProfileImage = (
        account.profile_image_url !== null
        && account.profile_image_url.trim() !== ""
        && !profileImageFailed
    );

    return (
        <section className={`intelboard-account-column${selected ? " is-selected" : ""}`}>
            <button
                className="intelboard-account-header"
                onClick={onSelect}
                type="button"
            >
                <div className="intelboard-account-avatar">
                    {showProfileImage ? (
                        <img
                            alt=""
                            decoding="async"
                            loading="lazy"
                            onError={() => setProfileImageFailed(true)}
                            referrerPolicy="no-referrer"
                            src={account.profile_image_url ?? undefined}
                        />
                    ) : (
                        <span aria-hidden="true">
                            {accountInitials(account.planets_username)}
                        </span>
                    )}
                </div>
                <div>
                    <span>Planets.nu observer</span>
                    <h2>{account.planets_username}</h2>
                    <p>{orderedGames.filter(isRunning).length} running · {orderedGames.length} total games</p>
                </div>
                {selected && <strong className="intelboard-account-current">current</strong>}
            </button>

            {error !== null && orderedGames.length === 0 ? (
                <div className="intelboard-account-state is-error">{error}</div>
            ) : orderedGames.length === 0 ? (
                <div className="intelboard-account-state">No games for this observer.</div>
            ) : (
                <>
                    {error !== null && (
                        <div className="intelboard-account-warning">
                            Live Planets.nu game-list metadata is unavailable; showing known games. {error}
                        </div>
                    )}
                    <div className="intelboard-game-list">
                        {orderedGames.map((game) => (
                            <GameRow
                                account={account}
                                details={detailsByGameId.get(game.id)}
                                game={game}
                                key={game.id}
                            />
                        ))}
                    </div>
                </>
            )}
        </section>
    );
}

export function IntelboardGamePicker({
    user,
    onLogout,
}: IntelboardGamePickerProps) {
    const [accounts, setAccounts] = useState<PlanetsAccountResponse[]>([]);
    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [gamesByAccountId, setGamesByAccountId] = useState<Record<number, AccountGameSummary[]>>({});
    const [errorsByAccountId, setErrorsByAccountId] = useState<Record<number, string | null>>({});
    const [detailsByGameId, setDetailsByGameId] = useState<Map<number, GameDetailsResponse>>(new Map());
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
        if (accounts.length === 0) {
            setGamesByAccountId({});
            setDetailsByGameId(new Map());
            return () => { cancelled = true; };
        }

        async function loadAllGames(initial: boolean) {
            if (initial) setLoadingGames(true);
            setError(null);

            const results = await Promise.all(
                accounts.map(async (account) => {
                    try {
                        const response = await getAccountGames(account.id);
                        return {
                            accountId: account.id,
                            games: response.games as AccountGameSummary[] | null,
                            error: response.upstream_error,
                        };
                    } catch (reason) {
                        return {
                            accountId: account.id,
                            games: null as AccountGameSummary[] | null,
                            error: reason instanceof Error ? reason.message : "Failed to load games",
                        };
                    }
                }),
            );
            if (cancelled) return;

            const nextErrors: Record<number, string | null> = {};
            const gameIds = new Set<number>();
            for (const result of results) {
                nextErrors[result.accountId] = result.error;
                for (const game of result.games ?? []) gameIds.add(game.id);
            }

            const ids = Array.from(gameIds);
            const details = await Promise.allSettled(ids.map((gameId) => getGame(gameId)));
            if (cancelled) return;
            const refreshedDetails = new Map<number, GameDetailsResponse>();
            details.forEach((result, index) => {
                if (result.status === "fulfilled") refreshedDetails.set(ids[index], result.value);
            });

            setGamesByAccountId((previous) => {
                const next = { ...previous };
                for (const result of results) {
                    if (result.games !== null) next[result.accountId] = result.games;
                }
                return next;
            });
            setErrorsByAccountId(nextErrors);
            setDetailsByGameId((previous) => {
                const next = new Map(previous);
                for (const [gameId, detailsValue] of refreshedDetails) {
                    next.set(gameId, detailsValue);
                }
                return next;
            });
            if (initial) setLoadingGames(false);
        }

        void loadAllGames(true);
        const intervalId = window.setInterval(
            () => void loadAllGames(false),
            GAME_PICKER_REFRESH_INTERVAL_MS,
        );
        return () => {
            cancelled = true;
            window.clearInterval(intervalId);
        };
    }, [accounts]);

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
                    <p>Each linked observer keeps its own operational game list and turn state.</p>
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

            {loadingAccounts || loadingGames ? (
                <div className="intelboard-game-menu-state">Loading observers and games…</div>
            ) : error !== null ? (
                <div className="intelboard-game-menu-state is-error">{error}</div>
            ) : accounts.length === 0 ? (
                <div className="intelboard-game-menu-state">No active Planets.nu observers are linked.</div>
            ) : (
                <section className="intelboard-account-grid">
                    {accounts.map((account) => (
                        <AccountColumn
                            account={account}
                            detailsByGameId={detailsByGameId}
                            error={errorsByAccountId[account.id] ?? null}
                            games={gamesByAccountId[account.id] ?? []}
                            key={account.id}
                            onSelect={() => {
                                rememberObserverId(account.id);
                                setSelectedAccountId(account.id);
                            }}
                            selected={account.id === selectedAccountId}
                        />
                    ))}
                </section>
            )}
        </main>
    );
}
