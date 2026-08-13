import { CombatEventPanel as VcrPanel } from "./CombatEventPanelLegacy";
import { HostEventPanel } from "./HostEventPanel";
import { MapEventBridge } from "./MapEventBridge";
import { PlayerActivityPanel } from "./PlayerActivityPanel";

export function CombatEventPanel(props: Parameters<typeof VcrPanel>[0]) {
    return <>
        <VcrPanel {...props} />
        <MapEventBridge />
        <div style={{ position: "absolute", zIndex: 5, left: 12, bottom: 48, width: "min(360px, 48%)", display: "grid", gap: 6 }}>
            <HostEventPanel gameId={props.gameId} linkedAccountId={props.linkedAccountId} turn={props.turn} />
            <PlayerActivityPanel gameId={props.gameId} throughTurn={props.turn} />
        </div>
    </>;
}
