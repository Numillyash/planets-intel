import type { SelectedEntity } from "./mapModel";
import { shipRole } from "./mapModel";

/**
 * UI-level entity icon abstraction.
 *
 * The current artwork is intentionally original CSS geometry rather than a
 * copied Planets.nu asset. This component is the single replacement point for
 * a licensed icon pack if one becomes available later.
 */
export function EntityIcon({ selected }: { selected: SelectedEntity }) {
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
