import React, {
    type FormEvent,
    useEffect,
    useState,
} from "react";
import ReactDOM from "react-dom/client";

import {
    getCurrentUser,
    login,
    logout,
} from "./api/client";
import { DashboardApp } from "./features/dashboard/DashboardApp";
import { IntelboardGamePicker } from "./features/dashboard/IntelboardGamePicker";
import type { CurrentUserResponse } from "./types/api";
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
        return () => { cancelled = true; };
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

    // /intelboard is a bootstrap URL. Once the picker resolves an observer it
    // canonicalizes itself to /intelboard/<observer>. Keep both forms routed to
    // the picker; /intelboard/<observer>/<game> remains the dashboard route.
    const gamePickerRoute = /^\/intelboard(?:\/[^/]+)?\/?$/i.test(
        window.location.pathname,
    );
    if (gamePickerRoute) {
        return <IntelboardGamePicker onLogout={handleLogout} user={user} />;
    }

    return <DashboardApp onLogout={handleLogout} user={user} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
);