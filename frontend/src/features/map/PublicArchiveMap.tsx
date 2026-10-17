import { useRef, useState } from "react";
import type { PlayerInfo } from "../../types/api";
import type { PublicArchiveTurn } from "../../types/publicArchive";
import { EntityDetails } from "./EntityDetails";
import {
    IntelMapWorkspace,
    IntelMapStage,
    IntelMapDetails,
    IntelMapHelp,
    IntelMapLegend,
} from "./IntelMapWorkspace";
import { PixiMapCanvas } from "./PixiMapCanvas";
import type { PlanetLabelMode, SelectedEntity } from "./mapModel";
import "./map.css";

/**
 * The exact same operational Pixi map and detail panels as an owned sector.
 * The tagged source prevents any observer-specific API hook from running:
 * public_finished_archive has no linked observer, order or sharing capability.
 */
export function PublicArchiveMap({
    archive, players,
}: {
    archive: PublicArchiveTurn;
    players: PlayerInfo[];
}) {
    const fitViewRef = useRef<(() => void) | null>(null);
    const [selected, setSelected] = useState<SelectedEntity | null>(null);
    const [labelMode, setLabelMode] = useState<PlanetLabelMode>("none");

    return (
        <section className="panel intel-map-panel">
            <div className="panel-header intel-map-header">
                <div>
                    <h2>Intelligence map</h2>
                    <p>
                        Public completed archive · slot #{archive.player_slot_id}
                        {" · "}Turn {archive.turn} · source game/loadturn
                    </p>
                    <p className="intel-no-facts">
                        Historical player perspective, read-only. No privately
                        linked observer or order context.
                    </p>
                </div>
                <div className="intel-map-actions">
                    <span>{archive.counts.planets} planets</span>
                    <span>{archive.counts.ships} ships</span>
                    <span>{archive.counts.starbases} bases</span>
                    <label className="intel-label-control">
                        <span>Planet labels</span>
                        <select className="secondary-button"
                            value={labelMode}
                            onChange={(event) =>
                                setLabelMode(event.target.value as PlanetLabelMode)}>
                            <option value="none">None</option>
                            <option value="id">Number</option>
                            <option value="name">Name</option>
                        </select>
                    </label>
                    <button className="secondary-button" type="button"
                        onClick={() => fitViewRef.current?.()}>Fit view</button>
                </div>
            </div>
            <IntelMapWorkspace>
                <IntelMapStage>
                    <PixiMapCanvas
                        fitViewRef={fitViewRef}
                        intel={archive}
                        partnerPoints={[]}
                        labelMode={labelMode}
                        selected={selected}
                        onSelect={setSelected}
                    />
                    <IntelMapHelp />
                    <IntelMapLegend />
                </IntelMapStage>
                <IntelMapDetails>
                    <div className="eyebrow">Selected factual observation</div>
                    <EntityDetails
                        intel={archive}
                        players={players}
                        selected={selected}
                        onSelect={setSelected}
                    />
                    <div className="intel-provenance-note">
                        <strong>Provenance</strong>
                        <span>Planets.nu public archival loadturn</span>
                        <span>Slot #{archive.player_slot_id} · T{archive.turn}</span>
                        <span>Read-only · no linked observer and no private batch</span>
                    </div>
                </IntelMapDetails>
            </IntelMapWorkspace>
        </section>
    );
}
