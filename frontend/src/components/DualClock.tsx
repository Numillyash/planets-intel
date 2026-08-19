import { useEffect, useMemo, useState } from "react";

import "./dual-clock.css";

function formatClock(value: Date, timeZone?: string): string {
    return new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        ...(timeZone ? { timeZone } : {}),
    }).format(value);
}

function formatUtcOffset(value: Date): string {
    const total = -value.getTimezoneOffset();
    const sign = total >= 0 ? "+" : "-";
    const absolute = Math.abs(total);
    const hours = Math.floor(absolute / 60);
    const minutes = absolute % 60;
    return `UTC${sign}${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function DualClock() {
    const [now, setNow] = useState(() => new Date());
    const localZone = useMemo(
        () => Intl.DateTimeFormat().resolvedOptions().timeZone || "browser local",
        [],
    );

    useEffect(() => {
        const timer = window.setInterval(() => setNow(new Date()), 1000);
        return () => window.clearInterval(timer);
    }, []);

    return (
        <div
            aria-label={`Global UTC ${formatClock(now, "UTC")}; local ${formatClock(now)} ${localZone} ${formatUtcOffset(now)}`}
            className="dual-clock"
        >
            <span>
                <small>GLOBAL · UTC</small>
                <strong>{formatClock(now, "UTC")}</strong>
            </span>
            <span>
                <small>LOCAL · {localZone}</small>
                <strong>{formatClock(now)}</strong>
                <em>{formatUtcOffset(now)}</em>
            </span>
        </div>
    );
}
