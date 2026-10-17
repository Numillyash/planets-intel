import type { ReactNode } from "react";

/** The same operational map layout for owned and public archived observations.
 * Authorization and fetching are handled by the source adapters, not this view.
 */
export function IntelMapWorkspace({ children }: { children: ReactNode }) {
    return <div className="intel-map-layout">{children}</div>;
}

export function IntelMapStage({ children }: { children: ReactNode }) {
    return <div className="intel-map-stage-wrap">{children}</div>;
}

export function IntelMapDetails({ children }: { children: ReactNode }) {
    return <aside className="intel-map-details">{children}</aside>;
}

export function IntelMapHelp() {
    return <div className="intel-map-help">
        Drag to pan · wheel to zoom · orbit ring means ships are present
    </div>;
}

export function IntelMapLegend() {
    return <div className="intel-map-legend">
        <span><i className="legend-link" />≤ 81 ly</span>
        <span><i className="legend-planet" />Planet</span>
        <span><i className="legend-surveyed" />Surveyed · owner unknown</span>
        <span><i className="legend-starbase" />Planet + base</span>
        <span><i className="legend-orbit" />Ships in orbit</span>
        <span><i style={{ border: "1px solid #5c9cca", borderRadius: "50%", background: "rgba(63,127,174,.35)" }} />Nebula</span>
        <span><i style={{ border: "1px solid #d7e4f5", borderRadius: "50%", background: "rgba(215,228,245,.35)" }} />Star cluster</span>
        <span><i style={{ border: "1px solid #e8c95d", borderRadius: "50%", background: "rgba(231,189,61,.35)" }} />Ion storm</span>
        <span><i className="legend-freighter" />Freighter</span>
        <span><i className="legend-torpedo" />Torpedo</span>
        <span><i className="legend-carrier" />Carrier</span>
        <span><i className="legend-warship" />Combat</span>
    </div>;
}
