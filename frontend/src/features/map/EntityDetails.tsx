import type { LatestPrivateIntelResponse, PlayerInfo } from "../../types/api";
import type { SelectedEntity } from "./mapModel";
import { PlanetDetails } from "./PlanetDetails";
import { ShipDetails } from "./ShipDetails";
import { StarbaseDetails } from "./StarbaseDetails";

export function EntityDetails({
    selected,
    intel,
    players,
    onSelect,
}: {
    selected: SelectedEntity | null;
    intel: LatestPrivateIntelResponse;
    players: PlayerInfo[];
    onSelect: (entity: SelectedEntity) => void;
}) {
    if (selected === null) {
        return (
            <div className="intel-map-empty-selection">
                <strong>Select an entity</strong>
                <p>
                    Click a planet, ship, or orbit marker. Detailed private facts
                    are shown only when they exist in this observer's snapshot.
                </p>
            </div>
        );
    }

    if (selected.kind === "planet") {
        return (
            <PlanetDetails
                intel={intel}
                onSelect={onSelect}
                planet={selected.value}
                players={players}
            />
        );
    }

    if (selected.kind === "ship") {
        return (
            <ShipDetails
                intel={intel}
                onSelect={onSelect}
                players={players}
                ship={selected.value}
            />
        );
    }

    return (
        <StarbaseDetails
            intel={intel}
            onSelect={onSelect}
            starbase={selected.value}
        />
    );
}
