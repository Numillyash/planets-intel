import type { FullTankMassScenario, UniformBeamScenario } from "../../types/threat";
import { FactRow } from "./DetailPrimitives";

export function FullTankBeamScenarios({
    observedMass,
    hullMass,
    beamSlots,
    fullTank,
    candidates,
}: {
    observedMass: number | null;
    hullMass: number | null;
    beamSlots: number | null;
    fullTank: FullTankMassScenario | null | undefined;
    candidates: UniformBeamScenario[] | undefined;
}) {
    if (fullTank === null || fullTank === undefined) return null;

    const grouped = new Map<number, UniformBeamScenario[]>();
    for (const candidate of candidates ?? []) {
        const existing = grouped.get(candidate.beam_mass_total) ?? [];
        existing.push(candidate);
        grouped.set(candidate.beam_mass_total, existing);
    }
    const rows = [...grouped.entries()].sort((a, b) => a[0] - b[0]);

    return (
        <section data-testid="full-tank-beam-scenarios" style={{ marginTop: 11 }}>
            <strong style={{ fontSize: 12 }}>Fighters by beam type · hypothetical</strong>
            <p className="intel-no-facts" style={{ marginTop: 5 }}>
                Conditional on a full fuel tank, every beam slot filled with the same weapon,
                and no other cargo. These are upper limits, not observed fighter counts.
            </p>
            {!fullTank.feasible ? (
                <p className="intel-no-facts" style={{ marginTop: 5 }}>
                    Full fuel tank is incompatible with the observed mass.
                </p>
            ) : (
                <>
                    <dl className="intel-fact-list" style={{ marginTop: 5 }}>
                        <FactRow label="Assumed fuel" value={`${fullTank.assumed_fuel} kt (NOT observed)`} />
                        <FactRow label="Mass after hull and fuel" value={
                            observedMass !== null && hullMass !== null
                                ? `${observedMass} − ${hullMass} − ${fullTank.assumed_fuel} = ${fullTank.remaining_mass_ceiling} kt`
                                : `${fullTank.remaining_mass_ceiling} kt`
                        } />
                        <FactRow label="Beam weapons assumed" value={beamSlots !== null ? `${beamSlots} identical beams` : "—"} />
                    </dl>
                    <div className="intel-orbit-list" style={{ marginTop: 6 }}>
                        {rows.map(([beamMass, group]) => (
                            <div className="intel-orbit-item" key={beamMass}
                                style={{ cursor: "default", alignItems: "flex-start" }}>
                                <span className="intel-orbit-symbol legend-orbit" style={{ marginTop: 3 }} />
                                <span style={{ minWidth: 0 }}>
                                    <strong>{group.map((item) => item.beam_name).join(" / ")}</strong>
                                    <small>
                                        {beamMass} kt beams · {group[0].full_tank_compatible
                                            ? `fighters ≤ ${group[0].fighter_ceiling}`
                                            : "impossible with a full tank"}
                                    </small>
                                </span>
                            </div>
                        ))}
                    </div>
                    {rows.length === 0 && (
                        <p className="intel-no-facts">No mass-qualified beam alternatives in the game catalog.</p>
                    )}
                </>
            )}
            <p className="intel-no-facts" style={{ marginTop: 6 }}>
                Assumes 1 kt per fighter; any cargo reduces these limits.
                Installed beam count, beam type, actual fuel and enemy fighters remain unconfirmed.
                Engine mass is already included in the hull.
            </p>
        </section>
    );
}
