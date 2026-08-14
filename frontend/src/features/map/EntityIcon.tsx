import { useEffect, useMemo, useState } from "react";

import { privateHullAssetUrl } from "../../lib/privateAssets";
import type { SelectedEntity } from "./mapModel";
import { shipRole } from "./mapModel";
import "./private-assets.css";

const MAX_ARTWORK_ATTEMPTS = 3;

export function EntityIcon({ selected }: { selected: SelectedEntity }) {
    const source = selected.kind === "ship"
        ? privateHullAssetUrl(selected.value.hull_id, selected.value.payload)
        : null;
    const [attempt, setAttempt] = useState(0);
    const [loaded, setLoaded] = useState(false);
    const [imageFailed, setImageFailed] = useState(false);

    useEffect(() => {
        setAttempt(0);
        setLoaded(false);
        setImageFailed(false);
    }, [source]);

    const requestSource = useMemo(() => {
        if (source === null) return null;
        if (attempt === 0) return source;
        const separator = source.includes("?") ? "&" : "?";
        return `${source}${separator}retry=${attempt}`;
    }, [attempt, source]);

    if (selected.kind === "ship" && requestSource !== null && !imageFailed) {
        const role = shipRole(selected.value);
        return (
            <span
                aria-hidden="true"
                className="operational-entity-icon operational-entity-icon-hull"
            >
                <span
                    className={
                        `operational-entity-icon-hull-fallback is-${role}`
                        + (loaded ? " is-hidden" : "")
                    }
                />
                <img
                    alt=""
                    draggable={false}
                    hidden={!loaded}
                    onError={() => {
                        setLoaded(false);
                        if (attempt + 1 < MAX_ARTWORK_ATTEMPTS) {
                            window.setTimeout(
                                () => setAttempt((value) => value + 1),
                                450 * (attempt + 1),
                            );
                        } else {
                            setImageFailed(true);
                        }
                    }}
                    onLoad={() => setLoaded(true)}
                    src={requestSource}
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
