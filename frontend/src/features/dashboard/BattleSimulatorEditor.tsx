import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";
import {
    intValue,
    isGalacticPowerEligible,
    normalizeShipForRace,
    raceLabel,
    rebuildPlanet,
    textValue,
    type MaterializedCombatant,
    type PlanetSetup,
    type ShipSetup,
} from "./battleSimulatorModel";

export function NumberInput({
    label,
    value,
    onChange,
    min = 0,
    max,
    disabled = false,
}: {
    label: string;
    value: number;
    onChange: (value: number) => void;
    min?: number;
    max?: number;
    disabled?: boolean;
}) {
    return (
        <label className="battle-sim-field">
            <span>{label}</span>
            <input
                className="battle-sim-input"
                disabled={disabled}
                max={max}
                min={min}
                onChange={(event) => {
                    const parsed = Number(event.target.value);
                    if (!Number.isFinite(parsed)) return;
                    const upper = max === undefined ? parsed : Math.min(max, parsed);
                    onChange(Math.trunc(Math.max(min, upper)));
                }}
                type="number"
                value={value}
            />
        </label>
    );
}

function RaceSelect({
    catalog,
    raceId,
    onChange,
}: {
    catalog: GameRuleCatalogResponse;
    raceId: number | null;
    onChange: (raceId: number | null) => void;
}) {
    return (
        <label className="battle-sim-field">
            <span>Race / crew</span>
            <select
                className="battle-sim-select"
                onChange={(event) => onChange(
                    event.target.value === "" ? null : Number(event.target.value),
                )}
                value={raceId ?? ""}
            >
                <option value="">No racial bonus</option>
                {catalog.races.map((record) => {
                    const id = intValue(record, "id");
                    if (id === null) return null;
                    return (
                        <option key={id} value={id}>
                            {textValue(record, "name", "shortname") ?? `Race #${id}`}
                        </option>
                    );
                })}
            </select>
        </label>
    );
}

function ModifierToggle({
    label,
    enabled,
    onChange,
    detail,
}: {
    label: string;
    enabled: boolean;
    onChange: (enabled: boolean) => void;
    detail?: string;
}) {
    return (
        <label className="battle-sim-toggle-field" title={detail}>
            <span>{label}</span>
            <input
                checked={enabled}
                onChange={(event) => onChange(event.target.checked)}
                type="checkbox"
            />
            <strong>{enabled ? "Enabled" : "Disabled"}</strong>
        </label>
    );
}

function ShipEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    if (value.setup.kind !== "ship") return null;
    const setup: ShipSetup = value.setup;
    const c = value.combatant;
    const galacticPowerEligible = isGalacticPowerEligible(
        catalog,
        c.hull_id,
        c.race_id,
    );

    const normalizedWith = (
        patch: Partial<ShipSetup>,
        combatPatch: Partial<typeof c> = {},
    ) => {
        const next: MaterializedCombatant = {
            ...value,
            setup: { ...setup, ...patch },
            combatant: { ...c, ...combatPatch },
        };
        onChange(normalizeShipForRace(next, next.combatant.race_id));
    };

    return (
        <div className="battle-sim-editor-body">
            <div className="battle-sim-fields battle-sim-fields-4">
                <RaceSelect
                    catalog={catalog}
                    onChange={(raceId) => onChange(normalizeShipForRace(value, raceId))}
                    raceId={c.race_id}
                />
                <NumberInput
                    label="Shield %"
                    max={100}
                    onChange={(shield) => onChange({
                        ...value,
                        combatant: { ...c, shield },
                    })}
                    value={c.shield}
                />
                <NumberInput
                    label="Damage %"
                    max={9999}
                    onChange={(damage) => normalizedWith({}, { damage })}
                    value={c.damage}
                />
                <NumberInput
                    label="Crew"
                    max={100000}
                    onChange={(crew) => onChange({
                        ...value,
                        combatant: { ...c, crew },
                    })}
                    value={c.crew}
                />
            </div>

            <div className="battle-sim-derived-strip">
                <span>Hull mass <strong>{setup.baseMass} KT</strong></span>
                <span>Combat mass <strong>{c.mass} KT</strong></span>
                <span>
                    Effective weapons
                    <strong> {c.beam_count}B / {c.launcher_count}T / {c.bay_count} bays</strong>
                </span>
                <span>Race <strong>{raceLabel(catalog, c.race_id)}</strong></span>
                {c.federation_crew_bonus && <span><strong>Fed Crew Bonus</strong></span>}
                {c.lizard_crew_bonus && <span><strong>Lizard Crew Bonus</strong></span>}
                {c.galactic_power && <span><strong>Galactic Power · force left</strong></span>}
            </div>

            {(
                c.race_id === 1
                || c.race_id === 2
                || c.race_id === 4
                || c.race_id === 5
                || galacticPowerEligible
            ) && (
                <div className="battle-sim-fields battle-sim-fields-3">
                    {c.race_id === 1 && (
                        <ModifierToggle
                            detail="+50 KT combat mass, +3 carrier bays, full weapons despite damage, and shield recovery between sequential fights."
                            enabled={c.federation_crew_bonus}
                            label="Federation Crew Bonus"
                            onChange={(enabled) => normalizedWith(
                                {},
                                { federation_crew_bonus: enabled },
                            )}
                        />
                    )}
                    {c.race_id === 2 && (
                        <ModifierToggle
                            detail="Allows the ship to survive to 150% damage against enemy ships. It does not apply against planets."
                            enabled={c.lizard_crew_bonus}
                            label="Lizard 150% Crew Bonus"
                            onChange={(enabled) => normalizedWith(
                                {},
                                { lizard_crew_bonus: enabled },
                            )}
                        />
                    )}
                    {c.race_id === 4 && (
                        <ModifierToggle
                            detail="Optional advantage; not active in Classic settings."
                            enabled={c.beam_charge_rate > 1}
                            label="Fury 2× beam recharge"
                            onChange={(enabled) => onChange({
                                ...value,
                                combatant: {
                                    ...c,
                                    beam_charge_rate: enabled ? 2 : 1,
                                },
                            })}
                        />
                    )}
                    {c.race_id === 5 && (
                        <ModifierToggle
                            enabled={c.beam_kill_rate > 1}
                            label="Privateer 3× beam crew kill"
                            onChange={(enabled) => onChange({
                                ...value,
                                combatant: {
                                    ...c,
                                    beam_kill_rate: enabled ? 3 : 1,
                                },
                            })}
                        />
                    )}
                    {galacticPowerEligible && (
                        <ModifierToggle
                            detail="When active, an Evil Empire Gorbie must fight from the left side. Disabled by default in Campaign; active in new Standard games."
                            enabled={c.galactic_power}
                            label="Galactic Power · force left"
                            onChange={(enabled) => onChange({
                                ...value,
                                combatant: {
                                    ...c,
                                    galactic_power: enabled,
                                },
                            })}
                        />
                    )}
                </div>
            )}

            {setup.physicalBeams > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput
                        label="Installed beams"
                        max={10}
                        onChange={(physicalBeams) => normalizedWith({ physicalBeams })}
                        value={setup.physicalBeams}
                    />
                    <label className="battle-sim-field battle-sim-field-wide">
                        <span>Beam weapon</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => onChange({
                                ...value,
                                combatant: {
                                    ...c,
                                    beam_id: Number(event.target.value),
                                },
                            })}
                            value={c.beam_id}
                        >
                            <option value={0}>Unknown / none</option>
                            {catalog.beams.map((record) => {
                                const id = intValue(record, "id");
                                if (id === null) return null;
                                return (
                                    <option key={id} value={id}>
                                        {textValue(record, "name") ?? `Beam #${id}`}
                                    </option>
                                );
                            })}
                        </select>
                    </label>
                </div>
            )}

            {setup.physicalLaunchers > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput
                        label="Installed launchers"
                        max={10}
                        onChange={(physicalLaunchers) => normalizedWith({ physicalLaunchers })}
                        value={setup.physicalLaunchers}
                    />
                    <label className="battle-sim-field battle-sim-field-wide">
                        <span>Torpedo weapon</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => onChange({
                                ...value,
                                combatant: {
                                    ...c,
                                    torpedo_id: Number(event.target.value),
                                },
                            })}
                            value={c.torpedo_id}
                        >
                            <option value={0}>Unknown / none</option>
                            {catalog.torpedos.map((record) => {
                                const id = intValue(record, "id");
                                if (id === null) return null;
                                return (
                                    <option key={id} value={id}>
                                        {textValue(record, "name") ?? `Torpedo #${id}`}
                                    </option>
                                );
                            })}
                        </select>
                    </label>
                    <NumberInput
                        label="Torpedoes"
                        max={100000}
                        onChange={(torpedoes) => onChange({
                            ...value,
                            combatant: { ...c, torpedoes },
                        })}
                        value={c.torpedoes}
                    />
                </div>
            )}

            {setup.physicalBays > 0 && (
                <div className="battle-sim-weapon-row">
                    <NumberInput
                        label="Hull fighter bays"
                        max={30}
                        onChange={(physicalBays) => normalizedWith({ physicalBays })}
                        value={setup.physicalBays}
                    />
                    <NumberInput
                        disabled
                        label="Effective bays"
                        onChange={() => {}}
                        value={c.bay_count}
                    />
                    <NumberInput
                        label="Fighters"
                        max={100000}
                        onChange={(fighters) => onChange({
                            ...value,
                            combatant: { ...c, fighters },
                        })}
                        value={c.fighters}
                    />
                </div>
            )}
        </div>
    );
}

function PlanetEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    if (value.setup.kind !== "planet") return null;
    const setup: PlanetSetup = value.setup;
    const c = value.combatant;
    const update = (patch: Partial<PlanetSetup>) => {
        onChange(rebuildPlanet(
            value,
            { ...setup, ...patch },
            c.race_id,
        ));
    };

    return (
        <div className="battle-sim-editor-body">
            <div className="battle-sim-fields battle-sim-fields-4">
                <RaceSelect
                    catalog={catalog}
                    onChange={(raceId) => onChange(rebuildPlanet(value, setup, raceId))}
                    raceId={c.race_id}
                />
                <NumberInput
                    label="Planet defense"
                    max={1000}
                    onChange={(planetDefense) => update({ planetDefense })}
                    value={setup.planetDefense}
                />
                <label className="battle-sim-toggle-field">
                    <span>Starbase</span>
                    <input
                        checked={setup.starbasePresent}
                        onChange={(event) => update({
                            starbasePresent: event.target.checked,
                        })}
                        type="checkbox"
                    />
                    <strong>{setup.starbasePresent ? "Present" : "None"}</strong>
                </label>
                {c.race_id === 4 && (
                    <ModifierToggle
                        detail="Fury 2× beam recharge applies to Fury planets too when the optional advantage is active."
                        enabled={c.beam_charge_rate > 1}
                        label="Fury 2× planet beams"
                        onChange={(enabled) => onChange(rebuildPlanet(
                            {
                                ...value,
                                combatant: {
                                    ...c,
                                    beam_charge_rate: enabled ? 2 : 1,
                                },
                            },
                            setup,
                            c.race_id,
                        ))}
                    />
                )}
            </div>

            {setup.starbasePresent && (
                <>
                    <div className="battle-sim-fields battle-sim-fields-4">
                        <NumberInput
                            label="Starbase defense"
                            max={1000}
                            onChange={(starbaseDefense) => update({ starbaseDefense })}
                            value={setup.starbaseDefense}
                        />
                        <label className="battle-sim-field">
                            <span>Starbase beam tech</span>
                            <select
                                className="battle-sim-select"
                                onChange={(event) => update({
                                    starbaseBeamTech: Number(event.target.value),
                                })}
                                value={setup.starbaseBeamTech}
                            >
                                <option value={0}>0 / none</option>
                                {catalog.beams.map((record) => {
                                    const id = intValue(record, "id");
                                    if (id === null) return null;
                                    return (
                                        <option key={id} value={id}>
                                            {id} · {textValue(record, "name") ?? `Beam #${id}`}
                                        </option>
                                    );
                                })}
                            </select>
                        </label>
                        <NumberInput
                            label="Starbase fighters"
                            max={100000}
                            onChange={(starbaseFighters) => update({ starbaseFighters })}
                            value={setup.starbaseFighters}
                        />
                        <NumberInput
                            label="Starbase accumulated damage %"
                            max={9999}
                            onChange={(starbaseDamage) => update({ starbaseDamage })}
                            value={setup.starbaseDamage}
                        />
                    </div>
                    <div className="battle-sim-fields battle-sim-fields-3">
                        <ModifierToggle
                            detail="Shielded starbases in a radiation halo receive +200 KT combat mass; Robots do not receive this bonus."
                            enabled={setup.starbaseMassBonus === 200}
                            label="Shielded base +200 KT"
                            onChange={(enabled) => update({
                                starbaseMassBonus: enabled ? 200 : 0,
                            })}
                        />
                    </div>
                </>
            )}

            <div className="battle-sim-derived-strip">
                <span>Combat mass <strong>{c.mass} KT</strong></span>
                <span>Beams <strong>{c.beam_count}</strong></span>
                <span>Beam tech <strong>{c.beam_id || "none"}</strong></span>
                <span>Bays <strong>{c.bay_count}</strong></span>
                <span>Total fighters <strong>{c.fighters}</strong></span>
                <span>Shield <strong>{c.shield}%</strong></span>
                {setup.starbasePresent && (
                    <span>Base damage <strong>{setup.starbaseDamage}%</strong></span>
                )}
            </div>

            {setup.planetDefense <= 0 && (
                <div className="battle-sim-warning">
                    Planet has no defense posts; the starbase cannot fight by itself.
                </div>
            )}
        </div>
    );
}

export function CombatantEditor({
    value,
    catalog,
    onChange,
}: {
    value: MaterializedCombatant;
    catalog: GameRuleCatalogResponse;
    onChange: (value: MaterializedCombatant) => void;
}) {
    return (
        <section className="battle-sim-editor">
            <header>
                <div>
                    <span className="eyebrow">SELECTED COMBATANT</span>
                    <h3>{value.combatant.name ?? "Combatant"}</h3>
                    <small>
                        {value.combatant.source_kind.replace("_", " ")}
                        {value.combatant.source_id === null
                            ? ""
                            : ` · #${value.combatant.source_id}`}
                    </small>
                </div>
            </header>

            {value.warnings.length > 0 && (
                <div className="battle-sim-warnings">
                    {value.warnings.map((warning) => (
                        <span key={warning}>⚠ {warning}</span>
                    ))}
                </div>
            )}

            {value.setup.kind === "ship" ? (
                <ShipEditor catalog={catalog} onChange={onChange} value={value} />
            ) : (
                <PlanetEditor catalog={catalog} onChange={onChange} value={value} />
            )}
        </section>
    );
}
