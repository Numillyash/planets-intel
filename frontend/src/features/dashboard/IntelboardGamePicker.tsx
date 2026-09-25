import { useEffect, useMemo, useState } from "react";

import {
    getAccountGames,
    getDashboardIntelShares,
    getGame,
    getPlanetsAccounts,
} from "../../api/client";
import { readRememberedObserverId, rememberObserverId } from "../../lib/observerSelection";
import { raceName } from "../../lib/races";
import type {
    AccountGameSummary,
    CurrentUserResponse,
    GameDetailsResponse,
    PlanetsAccountResponse,
    PlayerInfo,
} from "../../types/api";
import { AccountSettings } from "../account/AccountSettings";
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

type GameListMode = "active" | "archive";

interface GameObserverEntry {
    account: PlanetsAccountResponse;
    game: AccountGameSummary;
}

interface UnifiedGameEntry {
    game: AccountGameSummary;
    observers: GameObserverEntry[];
}

function gamePath(observer: string, gameId: number): string {
    return `/intelboard/${encodeURIComponent(observer)}/${gameId}`;
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
    return left !== null && left.localeCompare(right, undefined, { sensitivity: "accent" }) === 0;
}

function normalizedUsername(username: string): string {
    return username.trim().toLocaleLowerCase();
}

function shortUsername(username: string): string {
    const first = username.trim().split(/\s+/).filter(Boolean)[0] ?? "?";
    return first.length > 11 ? `${first.slice(0, 10)}…` : first;
}

function turnRailRaceLabel(raceId: number): string {
    switch (raceName(raceId)) {
        case "Federation": return "Fed";
        case "Lizards": return "Lizard";
        case "Bird Men": return "Bird";
        case "Fury": return "Fury";
        case "Privateers": return "Priv";
        case "Cyborg": return "Borg";
        case "Crystal People": return "Crystal";
        case "Evil Empire": return "Empire";
        case "Robots": return "Robot";
        case "Rebels": return "Rebel";
        case "Colonies": return "Colony";
        case "Horwasp": return "Wasp";
        default: return raceName(raceId);
    }
}

function isRunning(game: AccountGameSummary): boolean {
    return game.status_id === 2 || game.status_name.toLowerCase() === "running";
}

function isFinished(game: AccountGameSummary): boolean {
    return game.status_name.trim().toLowerCase() === "finished";
}

function gameStatusRank(game: AccountGameSummary): number {
    if (isRunning(game)) return 0;
    const normalized = game.status_name.trim().toLowerCase();
    if (normalized === "joining") return 1;
    if (normalized === "finished") return 3;
    return 2;
}

function compareGames(left: AccountGameSummary, right: AccountGameSummary): number {
    const statusDifference = gameStatusRank(left) - gameStatusRank(right);
    if (statusDifference !== 0) return statusDifference;
    if (right.turn !== left.turn) return right.turn - left.turn;
    return left.name.localeCompare(right.name);
}

function unifiedGames(
    accounts: PlanetsAccountResponse[],
    gamesByAccountId: Record<number, AccountGameSummary[]>,
): UnifiedGameEntry[] {
    const byGameId = new Map<number, UnifiedGameEntry>();

    for (const account of accounts) {
        for (const game of gamesByAccountId[account.id] ?? []) {
            const existing = byGameId.get(game.id);
            if (existing === undefined) {
                byGameId.set(game.id, {
                    game,
                    observers: [{ account, game }],
                });
                continue;
            }

            existing.observers.push({ account, game });
            if (game.turn > existing.game.turn) {
                existing.game = game;
            }
        }
    }

    return Array.from(byGameId.values())
        .map((entry) => ({
            ...entry,
            observers: [...entry.observers].sort((left, right) => (
                left.account.planets_username.localeCompare(right.account.planets_username)
            )),
        }))
        .sort((left, right) => compareGames(left.game, right.game));
}

function observerPlayer(
    details: GameDetailsResponse | undefined,
    account: PlanetsAccountResponse,
): PlayerInfo | null {
    if (details === undefined) return null;
    if (account.planets_account_id !== null) {
        const byId = details.players.find((player) => player.account_id === account.planets_account_id);
        if (byId !== undefined) return byId;
    }
    const username = normalizedUsername(account.planets_username);
    return details.players.find(
        (player) => normalizedUsername(player.username) === username,
    ) ?? null;
}

function observerGameStatus(
    observer: GameObserverEntry,
    details: GameDetailsResponse | undefined,
): number | null {
    // Public loadinfo may be retained from an older picker refresh when a later
    // request fails. Never let stale roster identity override newer canonical
    // observer membership evidence. Unknown remains unknown; absence is not death.
    if (details === undefined || details.game.turn !== observer.game.turn) {
        return observer.game.observer_status;
    }

    const player = observerPlayer(details, observer.account);
    return player?.status ?? observer.game.observer_status;
}

function allLocalObserversInactive(
    entry: UnifiedGameEntry,
    details: GameDetailsResponse | undefined,
): boolean {
    if (!isRunning(entry.game) || entry.observers.length === 0) return false;
    const statuses = entry.observers.map((observer) => observerGameStatus(observer, details));
    return statuses.every((status) => status !== null && status !== 1);
}

function isArchivedGame(
    entry: UnifiedGameEntry,
    details: GameDetailsResponse | undefined,
): boolean {
    return isFinished(entry.game) || allLocalObserversInactive(entry, details);
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
    return marker.trim() === "" ? null : "ready";
}

function compactTurnStates(
    accountTurnStatuses: readonly (string | null)[],
    loadInfoTurnStatus: string | null,
    slot: number,
    loadInfoMatchesTurn: boolean,
): PlayerTurnState[] {
    const states: PlayerTurnState[] = [];
    for (const turnStatus of accountTurnStatuses) {
        const account = officialTurnMarkerState(turnStatus?.[slot - 1]);
        if (account !== null) states.push(account);
    }
    if (loadInfoMatchesTurn) {
        const loadInfo = officialTurnMarkerState(loadInfoTurnStatus?.[slot - 1]);
        if (loadInfo !== null) states.push(loadInfo);
    }
    return states;
}

function gameTurnState(
    accountTurnStatuses: readonly (string | null)[],
    loadInfoTurnStatus: string | null,
    slot: number,
    player: PlayerInfo | null,
    loadInfoMatchesTurn: boolean,
): PlayerTurnState {
    const compactStates = compactTurnStates(
        accountTurnStatuses,
        loadInfoTurnStatus,
        slot,
        loadInfoMatchesTurn,
    );
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
    const loadInfo = loadInfoMatchesTurn ? loadInfoTurnState(player) : "unknown";
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

function missedTurnClass(player: PlayerInfo, state: PlayerTurnState, current: boolean): string {
    if (
        !current || player.status !== 1 || player.race_id >= 100
        || player.turns_missed === null || player.turns_missed <= 0
    ) return "";
    if (player.turns_missed >= 3) return " is-missed-critical";
    if (player.turns_missed === 2 && state !== "ready") return " is-missed-critical-risk";
    if (player.turns_missed === 2) return " is-missed-warning";
    return " is-missed-watch";
}

function missedTurnLabel(player: PlayerInfo, state: PlayerTurnState, current: boolean): string {
    if (
        !current || player.status !== 1 || player.race_id >= 100
        || player.turns_missed === null || player.turns_missed <= 0
    ) return "";
    const turns = player.turns_missed;
    const base = `${turns} consecutive missed turn${turns === 1 ? "" : "s"} reported by Planets.nu`;
    return turns === 2 && state !== "ready"
        ? `${base} · current turn incomplete · critical drop risk if another turn is missed`
        : base;
}

function PlayerTurnRail({
    details,
    gameTurn,
    slots,
    turnStatuses,
    managedUsernames,
}: {
    details: GameDetailsResponse | undefined;
    gameTurn: number;
    slots: number;
    turnStatuses: readonly (string | null)[];
    managedUsernames: ReadonlyMap<string, string>;
}) {
    const bySlot = new Map<number, PlayerInfo>();
    for (const player of details?.players ?? []) {
        if (player.slot_id > 0) bySlot.set(player.slot_id, player);
    }
    const loadInfoMatchesTurn = details?.game.turn === gameTurn;
    const loadInfoTurnStatus = loadInfoMatchesTurn ? details?.game.turn_status ?? null : null;
    const slotCount = Math.max(
        slots,
        ...turnStatuses.map((value) => value?.length ?? 0),
        loadInfoTurnStatus?.length ?? 0,
        ...Array.from(bySlot.keys()),
        0,
    );
    if (slotCount <= 0) return null;
    const densityClass = slotCount > 20 ? " is-very-dense" : slotCount > 14 ? " is-dense" : "";

    return (
        <div
            aria-label={`Race and turn status for ${slotCount} player slots`}
            className={`intelboard-turn-rail${densityClass}`}
        >
            {Array.from({ length: slotCount }, (_, index) => {
                const slot = index + 1;
                const player = bySlot.get(slot) ?? null;
                const state = gameTurnState(
                    turnStatuses,
                    loadInfoTurnStatus,
                    slot,
                    player,
                    loadInfoMatchesTurn,
                );
                const managedLabel = (
                    player === null
                    || state === "computer"
                    || state === "inactive"
                )
                    ? null
                    : managedUsernames.get(normalizedUsername(player.username)) ?? null;

                if (player === null) {
                    return (
                        <span className="intelboard-turn-slot" key={slot}>
                            <span
                                className={`intelboard-turn-cell is-${state}`}
                                title={`Slot ${slot} · no public player record · ${turnStateLabel(state)}`}
                            >
                                #{slot}
                            </span>
                        </span>
                    );
                }

                const missedClass = missedTurnClass(player, state, loadInfoMatchesTurn);
                const missedLabel = missedTurnLabel(player, state, loadInfoMatchesTurn);
                return (
                    <span
                        className={`intelboard-turn-slot${managedLabel === null ? "" : " is-managed"}`}
                        key={slot}
                    >
                        <span
                            className={`intelboard-turn-cell is-${state}${missedClass}`}
                            title={`${raceName(player.race_id)} / slot ${slot} / ${player.username.trim() || "computer"} · ${turnStateLabel(state)}${missedLabel ? ` · ${missedLabel}` : ""}`}
                        >
                            {turnRailRaceLabel(player.race_id)}
                        </span>
                        {managedLabel !== null && (
                            <span
                                className={`intelboard-managed-account-marker is-${state}`}
                                title={`${player.username} · ${turnStateLabel(state)}`}
                            >
                                <b aria-hidden="true">↑</b>{managedLabel}
                            </span>
                        )}
                    </span>
                );
            })}
        </div>
    );
}

function accountInitials(username: string): string {
    const words = username.trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return "?";
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toUpperCase();
}

function ObserverAvatar({ account }: { account: PlanetsAccountResponse }) {
    const [profileImageFailed, setProfileImageFailed] = useState(false);
    useEffect(() => setProfileImageFailed(false), [account.profile_image_url]);
    const showProfileImage = Boolean(
        account.profile_image_url?.trim() && !profileImageFailed,
    );

    return (
        <span className="intelboard-account-avatar">
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
                <span aria-hidden="true">{accountInitials(account.planets_username)}</span>
            )}
        </span>
    );
}

function ObserverChoice({
    account,
    games,
    selected,
    onSelect,
}: {
    account: PlanetsAccountResponse;
    games: AccountGameSummary[];
    selected: boolean;
    onSelect: () => void;
}) {
    return (
        <button
            className={`intelboard-observer-choice${selected ? " is-selected" : ""}`}
            onClick={onSelect}
            type="button"
        >
            <ObserverAvatar account={account} />
            <span className="intelboard-observer-choice-copy">
                <small>Planets.nu observer</small>
                <strong>{account.planets_username}</strong>
                <em>{games.filter(isRunning).length} running · {games.length} total</em>
            </span>
            {selected && <span className="intelboard-account-current">current</span>}
        </button>
    );
}

function GameCard({
    entry,
    details,
    selectedAccountId,
    managedUsernames,
}: {
    entry: UnifiedGameEntry;
    details: GameDetailsResponse | undefined;
    selectedAccountId: number | null;
    managedUsernames: ReadonlyMap<string, string>;
}) {
    const { game } = entry;
    const running = isRunning(game);
    const typeLabel = game.is_custom ? "Custom" : game.is_private ? "Private" : "Standard";
    const preferredObserver = (
        entry.observers.find(({ account }) => account.id === selectedAccountId)
        ?? entry.observers[0]
    );
    const currentTurnStatuses = entry.observers
        .filter(({ game: observerGame }) => observerGame.turn === game.turn)
        .map(({ game: observerGame }) => observerGame.turn_status);

    function openAs(account: PlanetsAccountResponse) {
        rememberObserverId(account.id);
        window.location.assign(gamePath(account.planets_username, game.id));
    }

    return (
        <article className="intelboard-game-card">
            <button
                className="intelboard-game-card-main"
                onClick={() => openAs(preferredObserver.account)}
                type="button"
            >
                <div className="intelboard-game-row-main">
                    <div className="intelboard-game-row-title">
                        <span className="intelboard-game-id">GAME #{game.id}</span>
                        <h2>{game.name}</h2>
                        <p>{game.short_description || typeLabel}</p>
                    </div>
                    <span className={`intelboard-game-status${running ? " is-running" : ""}`}>
                        {game.status_name}
                    </span>
                </div>
                <div className="intelboard-game-row-meta">
                    <span><strong>T{game.turn}</strong> turn</span>
                    <span><strong>{game.slots}</strong> slots</span>
                    <span><strong>{typeLabel}</strong></span>
                    <span className="intelboard-next-host">{game.time_to_host || "Host time unknown"}</span>
                </div>
            </button>

            <div className="intelboard-game-observer-bar">
                <span className="intelboard-game-observer-label">Open as</span>
                {entry.observers.map(({ account, game: observerGame }) => {
                    const player = observerPlayer(details, account);
                    const loadInfoMatchesTurn = details?.game.turn === observerGame.turn;
                    const loadInfoTurnStatus = loadInfoMatchesTurn
                        ? details?.game.turn_status ?? null
                        : null;
                    const ownState = !running
                        ? null
                        : player !== null
                            ? gameTurnState(
                                [observerGame.turn_status],
                                loadInfoTurnStatus,
                                player.slot_id,
                                player,
                                loadInfoMatchesTurn,
                            )
                            : observerGame.observer_status !== null
                                ? (observerGame.observer_status === 1 ? "unknown" : "inactive")
                                : null;
                    return (
                        <button
                            className={`intelboard-game-observer-chip${account.id === preferredObserver.account.id ? " is-preferred" : ""}`}
                            key={account.id}
                            onClick={() => openAs(account)}
                            title={`Open ${game.name} as ${account.planets_username}`}
                            type="button"
                        >
                            {ownState !== null && (
                                <i className={`is-${ownState}`} aria-hidden="true" />
                            )}
                            <strong>{account.planets_username}</strong>
                        </button>
                    );
                })}
            </div>

            {running && (
                <PlayerTurnRail
                    details={details}
                    gameTurn={game.turn}
                    managedUsernames={managedUsernames}
                    slots={game.slots}
                    turnStatuses={currentTurnStatuses}
                />
            )}
        </article>
    );
}

export function IntelboardGamePicker({ user, onLogout }: IntelboardGamePickerProps) {
    const [accounts, setAccounts] = useState<PlanetsAccountResponse[]>([]);
    const [accountsRevision, setAccountsRevision] = useState(0);
    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [gamesByAccountId, setGamesByAccountId] = useState<Record<number, AccountGameSummary[]>>({});
    const [errorsByAccountId, setErrorsByAccountId] = useState<Record<number, string | null>>({});
    const [detailsByGameId, setDetailsByGameId] = useState<Map<number, GameDetailsResponse>>(new Map());
    const [managedUsernames, setManagedUsernames] = useState<Map<string, string>>(new Map());
    const [gameListMode, setGameListMode] = useState<GameListMode>("active");
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
                const [response, sharesResponse] = await Promise.all([
                    getPlanetsAccounts(),
                    getDashboardIntelShares().catch(() => null),
                ]);
                if (cancelled) return;
                const active = response.accounts.filter((account) => account.is_active);
                const routeObserver = routedObserver(window.location.pathname);
                const routed = active.find((account) => sameObserver(routeObserver, account.planets_username)) ?? null;
                const rememberedId = readRememberedObserverId();
                const remembered = rememberedId === null
                    ? null
                    : active.find((account) => account.id === rememberedId) ?? null;
                const selected = routed ?? remembered ?? active[0] ?? null;

                const managed = new Map<string, string>();
                for (const account of active) {
                    managed.set(
                        normalizedUsername(account.planets_username),
                        shortUsername(account.planets_username),
                    );
                }
                for (const share of sharesResponse?.shares ?? []) {
                    if (share.status !== "active") continue;
                    for (const shareAccount of [share.account_a, share.account_b]) {
                        if (!shareAccount.approved || !shareAccount.is_active) continue;
                        managed.set(
                            normalizedUsername(shareAccount.planets_username),
                            shortUsername(shareAccount.planets_username),
                        );
                    }
                }

                setAccounts(active);
                setManagedUsernames(managed);
                setSelectedAccountId(selected?.id ?? null);
                if (selected !== null) rememberObserverId(selected.id);
                if (window.location.pathname !== "/intelboard") {
                    window.history.replaceState(
                        null,
                        "",
                        `/intelboard${window.location.search}${window.location.hash}`,
                    );
                }
            } catch (reason) {
                if (!cancelled) {
                    setError(reason instanceof Error ? reason.message : "Failed to load linked Planets.nu accounts");
                }
            } finally {
                if (!cancelled) setLoadingAccounts(false);
            }
        }
        void loadAccounts();
        return () => { cancelled = true; };
    }, [accountsRevision]);

    useEffect(() => {
        if (selectedAccountId !== null) rememberObserverId(selectedAccountId);
    }, [selectedAccountId]);

    useEffect(() => {
        let cancelled = false;
        if (accounts.length === 0) {
            setGamesByAccountId({});
            setErrorsByAccountId({});
            setDetailsByGameId(new Map());
            setLoadingGames(false);
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
                for (const [gameId, detailsValue] of refreshedDetails) next.set(gameId, detailsValue);
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

    const games = useMemo(
        () => unifiedGames(accounts, gamesByAccountId),
        [accounts, gamesByAccountId],
    );

    const { activeGames, archivedGames } = useMemo(() => {
        const active: UnifiedGameEntry[] = [];
        const archive: UnifiedGameEntry[] = [];
        for (const entry of games) {
            if (isArchivedGame(entry, detailsByGameId.get(entry.game.id))) {
                archive.push(entry);
            } else {
                active.push(entry);
            }
        }
        return { activeGames: active, archivedGames: archive };
    }, [games, detailsByGameId]);

    const visibleGames = gameListMode === "archive" ? archivedGames : activeGames;

    const gameListWarnings = useMemo(() => accounts.flatMap((account) => {
        const accountError = errorsByAccountId[account.id] ?? null;
        return accountError === null
            ? []
            : [`${account.planets_username}: ${accountError}`];
    }), [accounts, errorsByAccountId]);

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
                    <p>Games are shown once. Choose the observer only when a game is opened.</p>
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

            <div className="intelboard-account-settings-wrap">
                <AccountSettings
                    accounts={accounts}
                    onAccountsChanged={() => setAccountsRevision((value) => value + 1)}
                />
            </div>

            {loadingAccounts || loadingGames ? (
                <div className="intelboard-game-menu-state">Loading observers and games…</div>
            ) : error !== null ? (
                <div className="intelboard-game-menu-state is-error">{error}</div>
            ) : accounts.length === 0 ? (
                <div className="intelboard-game-menu-state">
                    No active Planets.nu observers are linked. Open Account settings above to link one.
                </div>
            ) : (
                <>
                    <section className="intelboard-observer-strip" aria-label="Local Planets.nu observers">
                        {accounts.map((account) => (
                            <ObserverChoice
                                account={account}
                                games={gamesByAccountId[account.id] ?? []}
                                key={account.id}
                                onSelect={() => setSelectedAccountId(account.id)}
                                selected={account.id === selectedAccountId}
                            />
                        ))}
                    </section>

                    {gameListWarnings.length > 0 && (
                        <div className="intelboard-account-warning intelboard-global-warning">
                            Live game-list metadata is unavailable for some observers; cached entries remain visible. {gameListWarnings.join(" · ")}
                        </div>
                    )}

                    {games.length === 0 ? (
                        <div className="intelboard-game-menu-state">No games were found for the linked observers.</div>
                    ) : (
                        <>
                            <nav className="intelboard-game-tabs" aria-label="Game categories">
                                <button
                                    aria-selected={gameListMode === "active"}
                                    className={`intelboard-game-tab${gameListMode === "active" ? " is-selected" : ""}`}
                                    onClick={() => setGameListMode("active")}
                                    role="tab"
                                    type="button"
                                >
                                    Active <span>{activeGames.length}</span>
                                </button>
                                <button
                                    aria-selected={gameListMode === "archive"}
                                    className={`intelboard-game-tab${gameListMode === "archive" ? " is-selected" : ""}`}
                                    onClick={() => setGameListMode("archive")}
                                    role="tab"
                                    type="button"
                                >
                                    Archive <span>{archivedGames.length}</span>
                                </button>
                                <p>
                                    {gameListMode === "archive"
                                        ? "Finished games and running games where every linked local observer is inactive / dead."
                                        : "Running and joining games with at least one local observer not factually known inactive."}
                                </p>
                            </nav>

                            {visibleGames.length === 0 ? (
                                <div className="intelboard-game-menu-state">
                                    {gameListMode === "archive"
                                        ? "No finished or locally eliminated games are known yet."
                                        : "No active games were found for the linked observers."}
                                </div>
                            ) : (
                                <section className="intelboard-game-grid">
                                    {visibleGames.map((entry) => (
                                        <GameCard
                                            details={detailsByGameId.get(entry.game.id)}
                                            entry={entry}
                                            key={entry.game.id}
                                            managedUsernames={managedUsernames}
                                            selectedAccountId={selectedAccountId}
                                        />
                                    ))}
                                </section>
                            )}
                        </>
                    )}
                </>
            )}
        </main>
    );
}
