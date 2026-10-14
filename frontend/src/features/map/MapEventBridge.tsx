import { useEffect } from "react";

const EVENT_SELECT = "dashboard-event-select";

function clickEventButton(vcrId: number): boolean {
    const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
    const target = buttons.find((button) =>
        button.textContent?.includes(`VCR #${vcrId} ·`),
    );
    if (target === undefined) return false;
    target.click();
    return true;
}

export function MapEventBridge() {
    useEffect(() => {
        const handleSelection = (rawEvent: Event) => {
            const detail = (rawEvent as CustomEvent<{ vcrId?: number }>).detail;
            if (typeof detail?.vcrId !== "number") return;

            if (clickEventButton(detail.vcrId)) return;

            const buttons = Array.from(
                document.querySelectorAll<HTMLButtonElement>("button"),
            );
            const opener = buttons.find((button) =>
                button.textContent?.trim().startsWith("VCRs ·"),
            );
            if (opener === undefined) return;

            opener.click();
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    clickEventButton(detail.vcrId as number);
                });
            });
        };

        window.addEventListener(EVENT_SELECT, handleSelection);
        return () => window.removeEventListener(EVENT_SELECT, handleSelection);
    }, []);

    return null;
}
