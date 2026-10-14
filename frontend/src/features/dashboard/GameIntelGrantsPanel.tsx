import { useEffect, useState, type FormEvent } from "react";
import {
    consentGameIntelGrant,
    getGameIntelGrants,
    requestGameIntelGrant,
    revokeGameIntelGrant,
    type GameIntelGrant,
    type GameIntelMode,
    type GameIntelScope,
} from "../../api/gameIntelGrants";

const OPTIONAL_SCOPES: Array<{
    id: GameIntelScope;
    title: string;
    description: string;
}> = [
    { id: "owned_unit_locations", title: "Owned object locations", description: "Positions not already visible in your Host turn" },
    { id: "third_party_contacts", title: "Third-party contacts", description: "Additional sightings of other empires" },
    { id: "combat_vcr_evidence", title: "Combat/VCR evidence", description: "Additional battle observations" },
    { id: "owned_planet_details", title: "Planets and economy", description: "Colonies, minerals, population and production" },
    { id: "owned_ship_details", title: "Ship details", description: "Ships, equipment and technical state" },
    { id: "financial_and_cargo", title: "Cargo and funds", description: "Transported resources, money and inventories" },
    { id: "ship_friendly_codes", title: "Ship Friendly Codes", description: "Codes normally omitted even by Full Alliance" },
    { id: "planet_friendly_codes", title: "Planet Friendly Codes", description: "Additional planet codes" },
    { id: "ship_orders", title: "Ship orders and navigation", description: "Missions, targets, enemies, warps and waypoints" },
    { id: "ship_transfers", title: "Ship transfer orders", description: "Transfers, including beams and other prepared orders" },
    { id: "starbase_orders_inventory", title: "Starbase orders and inventory", description: "Construction, stored hulls, parts and torpedoes" },
    { id: "planet_build_goals", title: "Planet plans", description: "Build goals and happiness-related plans" },
    { id: "ship_history", title: "Ship history", description: "Earlier movement and known past observations" },
    { id: "wormhole_scans", title: "Wormhole scans", description: "Additional scans not exposed by native diplomacy" },
    { id: "private_messages", title: "Private in-game messages", description: "May contain correspondence from third players" },
];

const BASELINE = [
    "The authenticated player's own turn data",
    "Any allied locations and sightings already supplied by the Host",
    "Any native Share Intel/Full Alliance VCR and object fields already supplied",
];

export function GameIntelGrantsPanel({
    gameId,
    linkedAccountId,
}: {
    gameId: number;
    linkedAccountId: number;
}) {
    const [grants, setGrants] = useState<GameIntelGrant[]>([]);
    const [mode, setMode] = useState<GameIntelMode>("native");
    const [target, setTarget] = useState("");
    const [selected, setSelected] = useState<GameIntelScope[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [revision, setRevision] = useState(0);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        void getGameIntelGrants(gameId)
            .then((items) => { if (!cancelled) setGrants(items); })
            .catch((reason: unknown) => {
                if (!cancelled) setError(
                    reason instanceof Error ? reason.message : "Unable to load game grants",
                );
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [gameId, revision]);

    function toggleScope(id: GameIntelScope, enabled: boolean) {
        setSelected((previous) => enabled
            ? [...previous.filter((scope) => scope !== id), id]
            : previous.filter((scope) => scope !== id));
    }

    async function createGrant(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (mode !== "unrestricted" || !target.trim() || selected.length === 0) {
            return;
        }
        if (selected.includes("private_messages")) {
            const acknowledged = window.confirm(
                "Private in-game messages may include text from players who did not " +
                "agree to redistribution. Record an explicit request to disclose " +
                "these messages for this game? This does NOT activate sharing yet.",
            );
            if (!acknowledged) return;
        }
        setBusy(true);
        setError(null);
        try {
            await requestGameIntelGrant(
                gameId, linkedAccountId, target.trim(), mode, selected,
            );
            setTarget("");
            setSelected([]);
            setRevision((old) => old + 1);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Cannot create request");
        } finally {
            setBusy(false);
        }
    }

    async function act(grant: GameIntelGrant, action: "accept" | "revoke") {
        const confirm = action === "accept"
            ? window.confirm(
                "Consent to the specifically listed categories for this game? " +
                "This only records consent and does not activate sharing. " +
                (grant.requested_scopes.includes("private_messages")
                    ? "The request includes private messages from third parties. "
                    : ""),
            )
            : window.confirm("Revoke this game-scoped agreement?");
        if (!confirm) return;
        setBusy(true);
        setError(null);
        try {
            if (action === "accept") {
                await consentGameIntelGrant(
                    gameId, grant.id, linkedAccountId,
                    grant.sharing_mode === "unrestricted",
                );
            } else {
                await revokeGameIntelGrant(gameId, grant.id, linkedAccountId);
            }
            setRevision((old) => old + 1);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Cannot update consent");
        } finally {
            setBusy(false);
        }
    }

    const checkStyle = { display: "flex", alignItems: "flex-start", gap: 9 } as const;
    const groupStyle = { display: "grid", gap: 9, padding: 12 } as const;

    return (
        <section className="panel">
            <div className="panel-header">
                <div>
                    <h2>Intelligence sharing — this game only</h2>
                    <p>
                        The Host-provided view is permanent. Extra access is an
                        explicit, revocable request per observer and game.
                    </p>
                </div>
            </div>

            <div style={groupStyle}>
                <strong>Native Planets.nu view — always retained</strong>
                {BASELINE.map((description) => (
                    <label key={description} style={checkStyle}>
                        <input checked disabled readOnly type="checkbox" />
                        <span>{description}</span>
                    </label>
                ))}
                <small className="subtitle">
                    These entries describe whatever your own Host turn already
                    provides; the actual revealed fields depend on current
                    upstream diplomacy. IntelBoard cannot disable or invent them.
                </small>
            </div>

            <form className="auth-form" onSubmit={(event) => void createGrant(event)}>
                <label>
                    <span>Sharing mode</span>
                    <select
                        className="secondary-button"
                        onChange={(event) => setMode(event.target.value as GameIntelMode)}
                        value={mode}
                    >
                        <option value="native">Native — Host-provided only</option>
                        <option value="unrestricted">Extended — choose extra fields</option>
                    </select>
                </label>

                {mode === "unrestricted" && (
                    <>
                        <label>
                            <span>Other player's linked Planets.nu username</span>
                            <input
                                autoComplete="off"
                                onChange={(event) => setTarget(event.target.value)}
                                placeholder="Exact linked Planets.nu username"
                                required
                                type="text"
                                value={target}
                            />
                        </label>
                        <fieldset style={groupStyle}>
                            <legend>Additional disclosure permissions — optional</legend>
                            {OPTIONAL_SCOPES.map((scope) => (
                                <label key={scope.id} style={checkStyle}>
                                    <input
                                        checked={selected.includes(scope.id)}
                                        onChange={(event) =>
                                            toggleScope(scope.id, event.target.checked)
                                        }
                                        type="checkbox"
                                    />
                                    <span>
                                        <strong>{scope.title}</strong>
                                        <small className="subtitle" style={{ display: "block" }}>
                                            {scope.description}
                                        </small>
                                    </span>
                                </label>
                            ))}
                        </fieldset>
                        <button
                            className="primary-button"
                            disabled={busy || selected.length === 0 || !target.trim()}
                            type="submit"
                        >
                            {busy ? "Saving…" : "Request extended consent"}
                        </button>
                    </>
                )}
            </form>

            <p className="subtitle" style={{ marginTop: 12 }}>
                Security hold: accepting an agreement does not yet permit reading
                another player's stored private turn. Full cross-player data
                projections are not active. Credentials are never shareable.
            </p>

            <h3>Requests in this game</h3>
            {loading ? (
                <p className="subtitle">Loading requests…</p>
            ) : grants.length === 0 ? (
                <p className="subtitle">No recorded consent requests.</p>
            ) : (
                <div style={groupStyle}>
                    {grants.map((grant) => {
                        const canAccept = grant.grantee_account_id === linkedAccountId &&
                            grant.status === "pending";
                        const canRevoke = grant.status !== "revoked" &&
                            (
                                grant.grantor_account_id === linkedAccountId ||
                                grant.grantee_account_id === linkedAccountId
                            );
                        return (
                            <div className="user-menu" key={grant.id} style={groupStyle}>
                                <strong>
                                    Agreement #{grant.id} · {grant.sharing_mode}
                                </strong>
                                <span className="subtitle">
                                    Linked observers #{grant.grantor_account_id}
                                    {" → "}{grant.grantee_account_id}
                                    {" · "}{grant.status.split("_").join(" ")}
                                    {" · verified T"}{grant.membership_verified_turn}
                                </span>
                                <div>
                                    {grant.requested_scopes.join(", ")}
                                </div>
                                <small className="subtitle">
                                    Private data access: blocked pending separate policy.
                                </small>
                                <div style={{ display: "flex", gap: 8 }}>
                                    {canAccept && (
                                        <button
                                            className="primary-button"
                                            disabled={busy}
                                            onClick={() => void act(grant, "accept")}
                                            type="button"
                                        >
                                            Confirm requested scope
                                        </button>
                                    )}
                                    {canRevoke && (
                                        <button
                                            className="secondary-button"
                                            disabled={busy}
                                            onClick={() => void act(grant, "revoke")}
                                            type="button"
                                        >
                                            Revoke
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
            {error !== null && (
                <p className="auth-error" role="alert">{error}</p>
            )}
        </section>
    );
}
