import { useState } from "react";

import { privateHullAssetUrl } from "../../lib/privateAssets";
import type { SelectedEntity } from "./mapModel";
import { shipRole } from "./mapModel";

export function EntityIcon({ selected }: { selected: SelectedEntity }) {
    const [imageFailed, setImageFailed] = useState(false);

    if (selected.kind === "ship") {
        const source = privateHullAssetUrl(selected.value.hull_id);
        if (source !== null && !imageFailed) {
            return (
                <span
                    aria-hidden="true"
                    className="operational-entity-icon operational-entity-icon-hull"
                >
                    <img
                        alt=""
                        onError={() => setImageFailed(true)}
                        src={source}
                    />
                </span>
            );
        }
    }

    let variant = selected.kind;
    if (selected.kind === "ship") {
        variant = `ship-${shipRole(selected.value)}` as typeof variant;
    }

    return (
        <span
            aria-hidden="true"
            className={`operational-entity-icon operational-entity-icon-${variant}`}
        >
            <span className="operational-entity-icon-core" />
        </span>
    );
}
