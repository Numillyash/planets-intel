import {
    type FormEvent,
    useState,
} from "react";

import {
    changePassword,
    linkPlanetsAccount,
    unlinkPlanetsAccount,
} from "../../api/client";
import type {
    PlanetsAccountResponse,
} from "../../types/api";


interface AccountSettingsProps {
    accounts: PlanetsAccountResponse[];
    onAccountsChanged: () => void;
}


export function AccountSettings({
    accounts,
    onAccountsChanged,
}: AccountSettingsProps) {
    const [planetsUsername, setPlanetsUsername] =
        useState("");
    const [planetsPassword, setPlanetsPassword] =
        useState("");
    const [linking, setLinking] =
        useState(false);
    const [linkError, setLinkError] =
        useState<string | null>(null);
    const [unlinkingId, setUnlinkingId] =
        useState<number | null>(null);

    const [currentPassword, setCurrentPassword] =
        useState("");
    const [newPassword, setNewPassword] =
        useState("");
    const [confirmPassword, setConfirmPassword] =
        useState("");
    const [changingPassword, setChangingPassword] =
        useState(false);
    const [passwordError, setPasswordError] =
        useState<string | null>(null);

    async function handleLink(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();
        setLinking(true);
        setLinkError(null);

        try {
            await linkPlanetsAccount(
                planetsUsername.trim(),
                planetsPassword,
            );

            setPlanetsUsername("");
            setPlanetsPassword("");
            onAccountsChanged();
        } catch (reason) {
            setLinkError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to link Planets.nu account",
            );
        } finally {
            setLinking(false);
        }
    }

    async function handleUnlink(
        account: PlanetsAccountResponse,
    ) {
        const confirmed = window.confirm(
            `Unlink Planets.nu account ${account.planets_username}?`,
        );

        if (!confirmed) {
            return;
        }

        setUnlinkingId(account.id);
        setLinkError(null);

        try {
            await unlinkPlanetsAccount(
                account.id
            );
            onAccountsChanged();
        } catch (reason) {
            setLinkError(
                reason instanceof Error
                    ? reason.message
                    : "Failed to unlink Planets.nu account",
            );
        } finally {
            setUnlinkingId(null);
        }
    }

    async function handlePasswordChange(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();
        setPasswordError(null);

        if (newPassword !== confirmPassword) {
            setPasswordError(
                "New password confirmation does not match",
            );
            return;
        }

        if (newPassword.length < 8) {
            setPasswordError(
                "New password must be at least 8 characters",
            );
            return;
        }

        setChangingPassword(true);

        try {
            await changePassword(
                currentPassword,
                newPassword,
            );

            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");

            window.location.reload();
        } catch (reason) {
            setPasswordError(
                reason instanceof Error
                    ? reason.message
                    : "Password change failed",
            );
            setChangingPassword(false);
        }
    }

    return (
        <details
            className="panel"
            style={{ marginTop: 0 }}
        >
            <summary
                style={{
                    cursor: "pointer",
                    padding: "17px 22px",
                    fontWeight: 700,
                }}
            >
                Account settings
            </summary>

            <div
                style={{
                    display: "grid",
                    gap: 24,
                    gridTemplateColumns:
                        "repeat(auto-fit, minmax(280px, 1fr))",
                    padding: "0 22px 22px",
                }}
            >
                <section>
                    <h2>Planets.nu accounts</h2>
                    <p className="subtitle">
                        The Planets.nu password is used only to obtain an API key and is not stored.
                    </p>

                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                            margin: "16px 0",
                        }}
                    >
                        {accounts.length === 0 ? (
                            <span className="subtitle">
                                No linked accounts yet.
                            </span>
                        ) : (
                            accounts.map((account) => (
                                <div
                                    key={account.id}
                                    className="user-menu"
                                    style={{
                                        justifyContent: "space-between",
                                    }}
                                >
                                    <div
                                        style={{
                                            alignItems: "flex-start",
                                        }}
                                    >
                                        <strong>
                                            {account.planets_username}
                                        </strong>
                                        <span className="user-label">
                                            linked account #{account.id}
                                        </span>
                                    </div>
                                    <button
                                        className="secondary-button"
                                        disabled={
                                            unlinkingId === account.id
                                        }
                                        onClick={() => {
                                            void handleUnlink(account);
                                        }}
                                        type="button"
                                    >
                                        {unlinkingId === account.id
                                            ? "Unlinking…"
                                            : "Unlink"}
                                    </button>
                                </div>
                            ))
                        )}
                    </div>

                    <form
                        className="auth-form"
                        onSubmit={handleLink}
                    >
                        <label>
                            <span>Planets.nu username</span>
                            <input
                                autoComplete="off"
                                disabled={linking}
                                onChange={(event) => {
                                    setPlanetsUsername(
                                        event.target.value,
                                    );
                                }}
                                required
                                type="text"
                                value={planetsUsername}
                            />
                        </label>

                        <label>
                            <span>Planets.nu password</span>
                            <input
                                autoComplete="off"
                                disabled={linking}
                                onChange={(event) => {
                                    setPlanetsPassword(
                                        event.target.value,
                                    );
                                }}
                                required
                                type="password"
                                value={planetsPassword}
                            />
                        </label>

                        {linkError && (
                            <div
                                className="auth-error"
                                role="alert"
                            >
                                {linkError}
                            </div>
                        )}

                        <button
                            className="primary-button"
                            disabled={
                                linking ||
                                !planetsUsername.trim() ||
                                !planetsPassword
                            }
                            type="submit"
                        >
                            {linking
                                ? "Linking…"
                                : "Link Planets.nu account"}
                        </button>
                    </form>
                </section>

                <section>
                    <h2>Local password</h2>
                    <p className="subtitle">
                        Changing it signs out every active Intel Client session for this user.
                    </p>

                    <form
                        className="auth-form"
                        onSubmit={handlePasswordChange}
                        style={{ marginTop: 16 }}
                    >
                        <label>
                            <span>Current password</span>
                            <input
                                autoComplete="current-password"
                                disabled={changingPassword}
                                onChange={(event) => {
                                    setCurrentPassword(
                                        event.target.value,
                                    );
                                }}
                                required
                                type="password"
                                value={currentPassword}
                            />
                        </label>

                        <label>
                            <span>New password</span>
                            <input
                                autoComplete="new-password"
                                disabled={changingPassword}
                                minLength={8}
                                onChange={(event) => {
                                    setNewPassword(
                                        event.target.value,
                                    );
                                }}
                                required
                                type="password"
                                value={newPassword}
                            />
                        </label>

                        <label>
                            <span>Confirm new password</span>
                            <input
                                autoComplete="new-password"
                                disabled={changingPassword}
                                minLength={8}
                                onChange={(event) => {
                                    setConfirmPassword(
                                        event.target.value,
                                    );
                                }}
                                required
                                type="password"
                                value={confirmPassword}
                            />
                        </label>

                        {passwordError && (
                            <div
                                className="auth-error"
                                role="alert"
                            >
                                {passwordError}
                            </div>
                        )}

                        <button
                            className="primary-button"
                            disabled={
                                changingPassword ||
                                !currentPassword ||
                                !newPassword ||
                                !confirmPassword
                            }
                            type="submit"
                        >
                            {changingPassword
                                ? "Changing password…"
                                : "Change password"}
                        </button>
                    </form>
                </section>
            </div>
        </details>
    );
}
