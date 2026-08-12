import {
    type FormEvent,
    useEffect,
    useState,
} from "react";

import {
    acceptDashboardIntelShare,
    getDashboardIntelShares,
    requestDashboardIntelShare,
    revokeDashboardIntelShare,
} from "../../api/client";
import type { PlanetsAccountResponse } from "../../types/api";
import type {
    DashboardIntelShareAccount,
    DashboardIntelShareResponse,
} from "../../types/intel";

function accountLabel(account: DashboardIntelShareAccount): string {
    const ownership = account.is_mine ? " · yours" : "";
    const approval = account.approved ? " · approved" : " · waiting";
    return `${account.planets_username}${ownership}${approval}`;
}

function ownedAccountForAction(
    share: DashboardIntelShareResponse,
): DashboardIntelShareAccount | null {
    return [share.account_a, share.account_b].find(
        (account) => account.is_mine && account.is_active,
    ) ?? null;
}

export function IntelSharingSettings({
    accounts,
    onSharesChanged,
}: {
    accounts: PlanetsAccountResponse[];
    onSharesChanged: () => void;
}) {
    const [shares, setShares] = useState<DashboardIntelShareResponse[]>([]);
    const [sourceAccountId, setSourceAccountId] = useState<number | null>(
        accounts[0]?.id ?? null,
    );
    const [targetUsername, setTargetUsername] = useState("");
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [busyShareId, setBusyShareId] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [revision, setRevision] = useState(0);

    useEffect(() => {
        if (
            sourceAccountId === null ||
            !accounts.some((account) => account.id === sourceAccountId)
        ) {
            setSourceAccountId(accounts[0]?.id ?? null);
        }
    }, [accounts, sourceAccountId]);

    useEffect(() => {
        let cancelled = false;

        async function loadShares() {
            setLoading(true);
            setError(null);

            try {
                const response = await getDashboardIntelShares();
                if (!cancelled) {
                    setShares(response.shares);
                }
            } catch (reason) {
                if (!cancelled) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : "Failed to load dashboard intel shares",
                    );
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadShares();
        return () => {
            cancelled = true;
        };
    }, [revision]);

    function refresh() {
        setRevision((value) => value + 1);
        onSharesChanged();
    }

    async function handleRequest(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (sourceAccountId === null) {
            return;
        }

        setSubmitting(true);
        setError(null);

        try {
            await requestDashboardIntelShare(
                sourceAccountId,
                targetUsername.trim(),
            );
            setTargetUsername("");
            refresh();
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to request dashboard intel sharing",
            );
        } finally {
            setSubmitting(false);
        }
    }

    async function handleAccept(
        share: DashboardIntelShareResponse,
        account: DashboardIntelShareAccount,
    ) {
        setBusyShareId(share.id);
        setError(null);

        try {
            await acceptDashboardIntelShare(
                share.id,
                account.linked_account_id,
            );
            refresh();
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to accept dashboard intel sharing",
            );
        } finally {
            setBusyShareId(null);
        }
    }

    async function handleRevoke(share: DashboardIntelShareResponse) {
        const owned = ownedAccountForAction(share);
        if (owned === null) {
            return;
        }

        const confirmed = window.confirm(
            `Revoke dashboard intel sharing between ${share.account_a.planets_username} and ${share.account_b.planets_username}?`,
        );
        if (!confirmed) {
            return;
        }

        setBusyShareId(share.id);
        setError(null);

        try {
            await revokeDashboardIntelShare(
                share.id,
                owned.linked_account_id,
            );
            refresh();
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to revoke dashboard intel sharing",
            );
        } finally {
            setBusyShareId(null);
        }
    }

    return (
        <section>
            <h2>Dashboard intel sharing</h2>
            <p className="subtitle">
                This is separate from Planets.nu diplomacy. Both linked accounts
                must consent before their stored factual snapshots are combined.
            </p>

            <form
                className="auth-form"
                onSubmit={handleRequest}
                style={{ marginTop: 16 }}
            >
                <label>
                    <span>Share from</span>
                    <select
                        className="secondary-button"
                        disabled={submitting || accounts.length === 0}
                        onChange={(event) =>
                            setSourceAccountId(Number(event.target.value))
                        }
                        value={sourceAccountId ?? ""}
                    >
                        {accounts.map((account) => (
                            <option key={account.id} value={account.id}>
                                {account.planets_username}
                            </option>
                        ))}
                    </select>
                </label>

                <label>
                    <span>Target Planets.nu username</span>
                    <input
                        autoComplete="off"
                        disabled={submitting || sourceAccountId === null}
                        onChange={(event) => setTargetUsername(event.target.value)}
                        placeholder="Exact linked Planets.nu username"
                        required
                        type="text"
                        value={targetUsername}
                    />
                </label>

                <button
                    className="primary-button"
                    disabled={
                        submitting ||
                        sourceAccountId === null ||
                        !targetUsername.trim()
                    }
                    type="submit"
                >
                    {submitting ? "Requesting…" : "Request intel sharing"}
                </button>
            </form>

            <div
                style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    marginTop: 16,
                }}
            >
                {loading ? (
                    <span className="subtitle">Loading sharing agreements…</span>
                ) : shares.length === 0 ? (
                    <span className="subtitle">No dashboard sharing agreements.</span>
                ) : (
                    shares.map((share) => {
                        const acceptAccounts = [
                            share.account_a,
                            share.account_b,
                        ].filter(
                            (account) =>
                                account.is_mine &&
                                account.is_active &&
                                !account.approved,
                        );

                        return (
                            <div
                                className="user-menu"
                                key={share.id}
                                style={{
                                    alignItems: "flex-start",
                                    flexDirection: "column",
                                }}
                            >
                                <div style={{ alignItems: "flex-start" }}>
                                    <strong>
                                        {share.account_a.planets_username}
                                        {" ⇄ "}
                                        {share.account_b.planets_username}
                                    </strong>
                                    <span className="user-label">
                                        {share.status === "active" ? "ACTIVE" : "PENDING"}
                                    </span>
                                    <span className="subtitle">
                                        {accountLabel(share.account_a)}
                                    </span>
                                    <span className="subtitle">
                                        {accountLabel(share.account_b)}
                                    </span>
                                </div>

                                <div
                                    style={{
                                        display: "flex",
                                        flexWrap: "wrap",
                                        gap: 8,
                                    }}
                                >
                                    {acceptAccounts.map((account) => (
                                        <button
                                            className="primary-button"
                                            disabled={busyShareId === share.id}
                                            key={account.linked_account_id}
                                            onClick={() => {
                                                void handleAccept(share, account);
                                            }}
                                            type="button"
                                        >
                                            Accept as {account.planets_username}
                                        </button>
                                    ))}
                                    {ownedAccountForAction(share) !== null && (
                                        <button
                                            className="secondary-button"
                                            disabled={busyShareId === share.id}
                                            onClick={() => {
                                                void handleRevoke(share);
                                            }}
                                            type="button"
                                        >
                                            Revoke
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {error && (
                <div
                    className="auth-error"
                    role="alert"
                    style={{ marginTop: 12 }}
                >
                    {error}
                </div>
            )}
        </section>
    );
}
