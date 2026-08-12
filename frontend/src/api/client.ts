import type {
    AccountGamesResponse,
    ChangePasswordResponse,
    CurrentUserResponse,
    GameDetailsResponse,
    LatestPrivateIntelResponse,
    LoginResponse,
    LogoutResponse,
    PlanetsAccountResponse,
    PlanetsAccountsResponse,
    ScoreHistoryResponse,
    UnlinkPlanetsAccountResponse,
} from "../types/api";
import type {
    CombinedPrivateIntelResponse,
    DashboardIntelShareResponse,
    DashboardIntelShareRevokeResponse,
    DashboardIntelSharesResponse,
} from "../types/intel";

async function parseErrorMessage(
    response: Response,
): Promise<string> {
    try {
        const payload = await response.json() as {
            detail?: string;
        };

        if (payload.detail) {
            return payload.detail;
        }
    } catch {
        // Fall back to the HTTP status text below.
    }

    return `${response.status} ${response.statusText}`;
}

async function apiGet<T>(url: string): Promise<T> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(
            `API request failed: ${await parseErrorMessage(response)}`,
        );
    }

    return response.json() as Promise<T>;
}

async function apiGetOptional<T>(
    url: string,
): Promise<T | null> {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (response.status === 404) {
        return null;
    }

    if (!response.ok) {
        throw new Error(
            `API request failed: ${await parseErrorMessage(response)}`,
        );
    }

    return response.json() as Promise<T>;
}

export async function getCurrentUser(): Promise<CurrentUserResponse | null> {
    const response = await fetch("/api/auth/me", {
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (response.status === 401) {
        return null;
    }

    if (!response.ok) {
        throw new Error(
            `Authentication check failed: ${await parseErrorMessage(response)}`,
        );
    }

    return response.json() as Promise<CurrentUserResponse>;
}

export async function login(
    username: string,
    password: string,
): Promise<CurrentUserResponse> {
    const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            username,
            password,
        }),
    });

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    const payload = await response.json() as LoginResponse;

    return payload.user;
}

export async function logout(): Promise<void> {
    const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(
            `Logout failed: ${await parseErrorMessage(response)}`,
        );
    }

    const payload = await response.json() as LogoutResponse;

    if (!payload.success) {
        throw new Error("Logout failed");
    }
}

export async function changePassword(
    currentPassword: string,
    newPassword: string,
): Promise<void> {
    const response = await fetch("/api/auth/password", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
        }),
    });

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    const payload = await response.json() as ChangePasswordResponse;

    if (!payload.success) {
        throw new Error("Password change failed");
    }
}

export function getPlanetsAccounts(): Promise<PlanetsAccountsResponse> {
    return apiGet<PlanetsAccountsResponse>(
        "/api/planets/accounts",
    );
}

export async function linkPlanetsAccount(
    username: string,
    password: string,
): Promise<PlanetsAccountResponse> {
    const response = await fetch("/api/planets/accounts", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            username,
            password,
        }),
    });

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    return response.json() as Promise<PlanetsAccountResponse>;
}

export async function unlinkPlanetsAccount(
    accountId: number,
): Promise<void> {
    const response = await fetch(
        `/api/planets/accounts/${accountId}`,
        {
            method: "DELETE",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        },
    );

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    const payload = await response.json() as UnlinkPlanetsAccountResponse;

    if (!payload.success) {
        throw new Error("Failed to unlink Planets.nu account");
    }
}

export function getDashboardIntelShares(): Promise<DashboardIntelSharesResponse> {
    return apiGet<DashboardIntelSharesResponse>(
        "/api/intel/shares",
    );
}

export async function requestDashboardIntelShare(
    sourceAccountId: number,
    targetPlanetsUsername: string,
): Promise<DashboardIntelShareResponse> {
    const response = await fetch("/api/intel/shares", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            source_account_id: sourceAccountId,
            target_planets_username: targetPlanetsUsername,
        }),
    });

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    return response.json() as Promise<DashboardIntelShareResponse>;
}

export async function acceptDashboardIntelShare(
    shareId: number,
    accountId: number,
): Promise<DashboardIntelShareResponse> {
    const response = await fetch(
        `/api/intel/shares/${shareId}/accept`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                account_id: accountId,
            }),
        },
    );

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    return response.json() as Promise<DashboardIntelShareResponse>;
}

export async function revokeDashboardIntelShare(
    shareId: number,
    accountId: number,
): Promise<void> {
    const response = await fetch(
        `/api/intel/shares/${shareId}?account_id=${accountId}`,
        {
            method: "DELETE",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        },
    );

    if (!response.ok) {
        throw new Error(
            await parseErrorMessage(response),
        );
    }

    const payload = await response.json() as DashboardIntelShareRevokeResponse;

    if (!payload.success) {
        throw new Error("Failed to revoke dashboard intel share");
    }
}

export function getAccountGames(
    accountId: number,
): Promise<AccountGamesResponse> {
    return apiGet<AccountGamesResponse>(
        `/api/planets/accounts/${accountId}/games`,
    );
}

export function getGame(
    gameId: number,
): Promise<GameDetailsResponse> {
    return apiGet<GameDetailsResponse>(
        `/api/games/${gameId}`,
    );
}

export function getScoreHistory(
    gameId: number,
): Promise<ScoreHistoryResponse | null> {
    return apiGetOptional<ScoreHistoryResponse>(
        `/api/games/${gameId}/scores/history`,
    );
}

export function getLatestPrivateIntel(
    gameId: number,
    linkedAccountId: number,
): Promise<LatestPrivateIntelResponse | null> {
    return apiGetOptional<LatestPrivateIntelResponse>(
        `/api/games/${gameId}/private-intel/latest?linked_account_id=${linkedAccountId}`,
    );
}

export async function refreshPrivateIntel(
    gameId: number,
    linkedAccountId: number,
): Promise<LatestPrivateIntelResponse> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/refresh?linked_account_id=${linkedAccountId}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        },
    );

    if (!response.ok) {
        throw new Error(
            `Private intel refresh failed: ${await parseErrorMessage(response)}`,
        );
    }

    return response.json() as Promise<LatestPrivateIntelResponse>;
}

export async function refreshAccessiblePrivateIntel(
    gameId: number,
): Promise<void> {
    const response = await fetch(
        `/api/games/${gameId}/private-intel/refresh-accessible`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        },
    );

    if (!response.ok) {
        throw new Error(
            `Private intel auto-refresh failed: ${await parseErrorMessage(response)}`,
        );
    }

    await response.json();
}

export function getCombinedPrivateIntel(
    gameId: number,
    linkedAccountId: number,
): Promise<CombinedPrivateIntelResponse | null> {
    return apiGetOptional<CombinedPrivateIntelResponse>(
        `/api/games/${gameId}/private-intel/combined?linked_account_id=${linkedAccountId}`,
    );
}
