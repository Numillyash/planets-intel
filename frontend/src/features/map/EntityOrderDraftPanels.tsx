import { useEffect, useMemo, useState } from "react";

import {
    discardPlanetOrderDraft,
    discardStarbaseOrderDraft,
    getPlanetOrderDraft,
    getStarbaseOrderDraft,
    savePlanetOrderDraft,
    saveStarbaseOrderDraft,
} from "../../api/orderDraft";
import type {
    PlanetOrderDraft,
    StarbaseOrderDraft,
    StarbasePrimaryOrder,
} from "../../types/orderDraft";
import "./order-draft.css";


const STARBASE_ORDERS: Array<{ value: StarbasePrimaryOrder; label: string }> = [
    { value: "none", label: "None" },
    { value: "refuel", label: "Refuel" },
    { value: "max_defense", label: "Max Defense" },
    { value: "load_torpedoes", label: "Load Torpedoes" },
    { value: "unload_freighters", label: "Unload Freighters" },
    { value: "repair_base", label: "Repair Base" },
    { value: "force_surrender", label: "Force A Surrender" },
];

function DraftHeader({ title }: { title: string }) {
    return (
        <div className="operational-intel-callout order-draft-callout">
            <strong>{title}</strong>
            <span>Local draft only. Nothing is sent to Planets.nu yet.</span>
        </div>
    );
}

export function PlanetOrderDraftPanel({
    gameId,
    linkedAccountId,
    turn,
    planetId,
    upstreamFriendlyCode,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    planetId: number;
    upstreamFriendlyCode: string | null;
}) {
    const [draft, setDraft] = useState<PlanetOrderDraft | null>(null);
    const [friendlyCode, setFriendlyCode] = useState(upstreamFriendlyCode ?? "");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        void getPlanetOrderDraft(gameId, linkedAccountId, turn, planetId)
            .then((value) => {
                if (cancelled) return;
                setDraft(value);
                setFriendlyCode(value?.friendly_code ?? upstreamFriendlyCode ?? "");
                setError(null);
            })
            .catch((reason) => {
                if (!cancelled) setError(reason instanceof Error ? reason.message : "Failed to load planet draft");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [gameId, linkedAccountId, planetId, turn, upstreamFriendlyCode]);

    const changed = friendlyCode !== (draft?.friendly_code ?? upstreamFriendlyCode ?? "");

    async function save() {
        setSaving(true);
        setError(null);
        try {
            const next = await savePlanetOrderDraft(
                gameId, linkedAccountId, turn, planetId, friendlyCode,
            );
            setDraft(next);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to save planet draft");
        } finally {
            setSaving(false);
        }
    }

    async function discard() {
        setSaving(true);
        setError(null);
        try {
            await discardPlanetOrderDraft(gameId, linkedAccountId, turn, planetId);
            setDraft(null);
            setFriendlyCode(upstreamFriendlyCode ?? "");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to discard planet draft");
        } finally {
            setSaving(false);
        }
    }

    if (loading) return <p className="intel-no-facts">Loading planet orders…</p>;

    return (
        <div className="order-draft-panel">
            <DraftHeader title={draft ? "Local planet orders" : "Plan this planet"} />
            {draft?.stale && <div className="order-draft-warning">Factual snapshot changed after this draft was saved.</div>}
            {error && <div className="order-draft-error">{error}</div>}
            <div className="order-draft-comparison">
                <div className="order-draft-row order-draft-row-heading">
                    <span>Order</span><span>Upstream</span><span>Draft</span>
                </div>
                <div className="order-draft-row">
                    <strong>Friendly code</strong>
                    <span>{upstreamFriendlyCode ?? "—"}</span>
                    <input
                        aria-label="Planet friendly code"
                        disabled={saving}
                        maxLength={3}
                        onChange={(event) => setFriendlyCode(event.target.value)}
                        value={friendlyCode}
                    />
                </div>
            </div>
            <div className="order-draft-actions">
                <button className="primary-button" disabled={saving || !changed || friendlyCode.length > 3} onClick={() => void save()} type="button">
                    {saving ? "Saving…" : "Save draft"}
                </button>
                {draft && <button className="secondary-button" disabled={saving} onClick={() => void discard()} type="button">Discard draft</button>}
            </div>
            {draft && <p className="order-draft-provenance">Draft based on factual batch #{draft.base_batch_id}.</p>}
        </div>
    );
}

export function StarbaseOrderDraftPanel({
    gameId,
    linkedAccountId,
    turn,
    starbaseId,
    planetId,
    upstreamPrimaryOrder,
    upstreamFriendlyCode,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    starbaseId: number;
    planetId: number;
    upstreamPrimaryOrder: string | null;
    upstreamFriendlyCode: string | null;
}) {
    const [baseDraft, setBaseDraft] = useState<StarbaseOrderDraft | null>(null);
    const [planetDraft, setPlanetDraft] = useState<PlanetOrderDraft | null>(null);
    const [primaryOrder, setPrimaryOrder] = useState<StarbasePrimaryOrder>("none");
    const [friendlyCode, setFriendlyCode] = useState(upstreamFriendlyCode ?? "");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        void Promise.all([
            getStarbaseOrderDraft(gameId, linkedAccountId, turn, starbaseId),
            getPlanetOrderDraft(gameId, linkedAccountId, turn, planetId),
        ]).then(([base, planet]) => {
            if (cancelled) return;
            setBaseDraft(base);
            setPlanetDraft(planet);
            setPrimaryOrder(base?.primary_order ?? "none");
            setFriendlyCode(planet?.friendly_code ?? upstreamFriendlyCode ?? "");
            setError(null);
        }).catch((reason) => {
            if (!cancelled) setError(reason instanceof Error ? reason.message : "Failed to load starbase orders");
        }).finally(() => {
            if (!cancelled) setLoading(false);
        });
        return () => { cancelled = true; };
    }, [gameId, linkedAccountId, planetId, starbaseId, turn, upstreamFriendlyCode]);

    const changedBase = primaryOrder !== (baseDraft?.primary_order ?? "none");
    const changedCode = friendlyCode !== (planetDraft?.friendly_code ?? upstreamFriendlyCode ?? "");
    const changed = useMemo(() => changedBase || changedCode, [changedBase, changedCode]);

    async function save() {
        if (!changed) return;
        setSaving(true);
        setError(null);
        try {
            const [base, planet] = await Promise.all([
                changedBase
                    ? saveStarbaseOrderDraft(gameId, linkedAccountId, turn, starbaseId, primaryOrder)
                    : Promise.resolve(baseDraft),
                changedCode
                    ? savePlanetOrderDraft(gameId, linkedAccountId, turn, planetId, friendlyCode)
                    : Promise.resolve(planetDraft),
            ]);
            setBaseDraft(base);
            setPlanetDraft(planet);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to save starbase draft");
        } finally {
            setSaving(false);
        }
    }

    async function discard() {
        setSaving(true);
        setError(null);
        try {
            await Promise.all([
                discardStarbaseOrderDraft(gameId, linkedAccountId, turn, starbaseId),
                discardPlanetOrderDraft(gameId, linkedAccountId, turn, planetId),
            ]);
            setBaseDraft(null);
            setPlanetDraft(null);
            setPrimaryOrder("none");
            setFriendlyCode(upstreamFriendlyCode ?? "");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Failed to discard starbase draft");
        } finally {
            setSaving(false);
        }
    }

    if (loading) return <p className="intel-no-facts">Loading starbase orders…</p>;

    return (
        <div className="order-draft-panel">
            <DraftHeader title={baseDraft || planetDraft ? "Local starbase orders" : "Plan this starbase"} />
            {(baseDraft?.stale || planetDraft?.stale) && <div className="order-draft-warning">Factual snapshot changed after this draft was saved.</div>}
            {error && <div className="order-draft-error">{error}</div>}
            <div className="order-draft-comparison">
                <div className="order-draft-row order-draft-row-heading"><span>Order</span><span>Upstream</span><span>Draft</span></div>
                <div className="order-draft-row">
                    <strong>Primary order</strong>
                    <span>{upstreamPrimaryOrder ?? "—"}</span>
                    <select aria-label="Starbase primary order" disabled={saving} onChange={(event) => setPrimaryOrder(event.target.value as StarbasePrimaryOrder)} value={primaryOrder}>
                        {STARBASE_ORDERS.map((order) => <option key={order.value} value={order.value}>{order.label}</option>)}
                    </select>
                </div>
                <div className="order-draft-row">
                    <strong>Friendly code</strong>
                    <span>{upstreamFriendlyCode ?? "—"}</span>
                    <input aria-label="Planet and starbase friendly code" disabled={saving} maxLength={3} onChange={(event) => setFriendlyCode(event.target.value)} value={friendlyCode} />
                </div>
            </div>
            <p className="order-draft-provenance">The starbase Friendly Code is the Friendly Code of planet #{planetId}; this editor intentionally stores it as one shared planet draft.</p>
            <div className="order-draft-actions">
                <button className="primary-button" disabled={saving || !changed || friendlyCode.length > 3} onClick={() => void save()} type="button">{saving ? "Saving…" : "Save draft"}</button>
                {(baseDraft || planetDraft) && <button className="secondary-button" disabled={saving} onClick={() => void discard()} type="button">Discard draft</button>}
            </div>
        </div>
    );
}
