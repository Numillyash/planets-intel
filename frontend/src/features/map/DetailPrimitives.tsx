import type { ReactNode } from "react";
import type { PlayerInfo } from "../../types/api";
import { formatInteger, formatPercent, type MineralFacts } from "./observationView";

export function playerName(
    ownerId: number | null,
    players: PlayerInfo[],
): string {
    if (ownerId === null || ownerId <= 0) {
        return "Unknown / unowned";
    }

    const player = players.find(
        (item) => item.slot_id === ownerId,
    );

    return player
        ? `${player.username} (slot ${ownerId})`
        : `Slot ${ownerId}`;
}


export function FactRow({
    label,
    value,
}: {
    label: string;
    value: string | number;
}) {
    return (
        <div className="intel-fact-row">
            <dt>{label}</dt>
            <dd>{value}</dd>
        </div>
    );
}


export function DetailSection({
    title,
    children,
    open = true,
}: {
    title: string;
    children: ReactNode;
    open?: boolean;
}) {
    return (
        <details className="intel-detail-section" open={open}>
            <summary>{title}</summary>
            <div className="intel-detail-section-body">
                {children}
            </div>
        </details>
    );
}


export function MineralRow({
    label,
    facts,
}: {
    label: string;
    facts: MineralFacts;
}) {
    return (
        <tr>
            <th>{label}</th>
            <td>{formatInteger(facts.surface)}</td>
            <td>{formatInteger(facts.ground)}</td>
            <td>{formatPercent(facts.density)}</td>
            <td>{formatInteger(facts.production)}</td>
        </tr>
    );
}
