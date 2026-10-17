import type { ReactNode } from "react";
import type { CurrentUserResponse } from "../../types/api";

export function GamePageHeader({
    title, subtitle, status, turn, slots, user, loggingOut = false,
    onLogout, extra,
}: {
    title: string;
    subtitle: string;
    status: string | null;
    turn: number | null;
    slots: number | null;
    user: CurrentUserResponse;
    loggingOut?: boolean;
    onLogout: () => void;
    extra?: ReactNode;
}) {
    return (
        <header className="topbar">
            <div>
                <div className="eyebrow">Planets.nu Intel</div>
                <h1>{title}</h1>
                <p className="subtitle">{subtitle}</p>
                {extra}
            </div>
            <div className="topbar-actions">
                {status !== null && (
                    <div className="game-status">
                        <span className="status-badge">{status}</span>
                        {turn !== null && <strong>Turn {turn}</strong>}
                        {slots !== null && <span>{slots} slots</span>}
                    </div>
                )}
                <div className="user-menu">
                    <div>
                        <span className="user-label">Signed in as</span>
                        <strong>{user.display_name}</strong>
                    </div>
                    <button className="secondary-button" type="button"
                        disabled={loggingOut} onClick={onLogout}>
                        {loggingOut ? "Signing out…" : "Sign out"}
                    </button>
                </div>
            </div>
        </header>
    );
}
