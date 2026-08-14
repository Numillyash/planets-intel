import { useEffect, useState } from "react";

import { privateHullAssetUrl } from "../../lib/privateAssets";
import type { SelectedEntity } from "./mapModel";
import { shipRole } from "./mapModel";
import "./private-assets.css";

export function EntityIcon({ selected }: { selected: SelectedEntity }) {
    const source = selected.kind === "ship"
        ? privateHullAssetUrl(selected.value.hull_id, selected.value.payload)
        : null;
    const [imageFailed, setImageFailed] = useState(false);

    useEffect(() => {
        setImageFailed(false);
    }, [source]);

    if (selected.kind === "ship" && source !== null && !imageFailed) {
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
