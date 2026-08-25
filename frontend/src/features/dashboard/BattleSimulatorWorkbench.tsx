import { useEffect, useMemo, useState } from "react";

import {
    runStandaloneBattle,
    runStandaloneBattleOdds,
    runStandaloneBattleSequence,
    runStandaloneBattleSequenceOdds,
    type BattleSimulatorOddsResponse,
    type BattleSimulatorRunResponse,
    type BattleSimulatorSequenceOddsResponse,
    type BattleSimulatorSequenceRunResponse,
    type RightBalanceMode,
} from "../../api/battleSimulator";
import type { GameRuleCatalogResponse } from "../../api/ruleCatalog";
import type { GameDetailsResponse } from "../../types/api";
import type { PrivateIntelMapResponse } from "../../types/intel";
import { CombatReplayPlayer } from "./CombatReplayPlayer";
import { BattleSimulatorAddPicker } from "./BattleSimulatorAddPicker";
import { CombatantEditor, NumberInput } from "./BattleSimulatorEditor";
import {
    candidateLabel,
    intValue,
    materializeCandidate,
    type CandidateKey,
    type MaterializedCombatant,
    type SideName,
} from "./battleSimulatorModel";

function QueueColumn({
    side,
    queue,
    selectedIndex,
    onSelect,
    onMove,
    onRemove,
}: {
    side: SideName;
    queue: MaterializedCombatant[];
    selectedIndex: number;
    onSelect: (index: number) => void;
    onMove: (index: number, delta: number) => void;
    onRemove: (index: number) => void;
}) {
    return (
        <section className="battle-sim-queue-column">
            <div className="battle-sim-queue-heading">
                <span>{side.toUpperCase()}</span>
                <strong>{queue.length} combatant{queue.length === 1 ? "" : "s"}</strong>
            </div>
            <div className="battle-sim-queue-list">
                {queue.map((item, index) => (
                    <div
                        className={`battle-sim-queue-card${selectedIndex === index ? " is-selected" : ""}`}
                        key={`${item.combatant.source_kind}-${item.combatant.source_id ?? "manual"}-${index}`}
                    >
                        <button
                            className="battle-sim-queue-select"
                            onClick={() => onSelect(index)}
                            type="button"
                        >
                            <span className="battle-sim-order">{index + 1}</span>
                            <span className="battle-sim-queue-card-main">
                                <strong>{item.combatant.name ?? "Combatant"}</strong>
                                <small>
                                    {item.setup.kind === "planet"
                                        ? `planet${item.setup.starbasePresent ? " + starbase" : ""}`
                                        : `${item.combatant.beam_count}B · ${item.combatant.launcher_count}T · ${item.combatant.bay_count} bays`}
                                    {item.combatant.galactic_power ? " · Galactic Power" : ""}
                                </small>
                            </span>
                        </button>
                        <span className="battle-sim-queue-actions">
                            <button
                                disabled={index === 0}
                                onClick={() => onMove(index, -1)}
                                title="Move up"
                                type="button"
                            >↑</button>
                            <button
                                disabled={index === queue.length - 1}
                                onClick={() => onMove(index, 1)}
                                title="Move down"
                                type="button"
                            >↓</button>
                            <button
                                disabled={queue.length <= 1}
                                onClick={() => onRemove(index)}
                                title="Remove"
                                type="button"
                            >×</button>
                        </span>
                    </div>
                ))}
            </div>
        </section>
    );
}

function OutcomeGrid({
    outcomes,
}: {
    outcomes: Array<{ outcome: string; count: number; percent: number }>;
}) {
    return (
        <div className="battle-sim-outcome-grid">
            {outcomes.map((item) => (
                <div key={item.outcome}>
                    <strong>{item.percent}%</strong>
                    <span>
                        {item.outcome
                            .replaceAll("_", " ")
                            .replaceAll("+", " + ")}
                    </span>
                    <small>{item.count.toLocaleString()} battles</small>
                </div>
            ))}
        </div>
    );
}

function MeanSideCard({
    label,
    name,
    side,
}: {
    label: string;
    name: string;
    side: NonNullable<BattleSimulatorOddsResponse["sides"]["left"]>;
}) {
    return (
        <article className="battle-sim-stat-card">
            <span>{label}</span>
            <h4>{name}</h4>
            <div className="battle-sim-stat-grid">
                <div><small>Survived</small><strong>{side.survived_percent}%</strong></div>
                <div><small>Destroyed</small><strong>{side.destroyed_percent}%</strong></div>
                <div><small>Captured</small><strong>{side.captured_percent}%</strong></div>
                <div><small>Avg shield</small><strong>{side.mean_final_shield}%</strong></div>
                <div><small>Avg damage</small><strong>{side.mean_final_damage}%</strong></div>
                <div><small>Avg crew</small><strong>{side.mean_final_crew}</strong></div>
                <div><small>Avg torps</small><strong>{side.mean_final_torpedoes}</strong></div>
                <div><small>Avg fighters</small><strong>{side.mean_final_fighters}</strong></div>
            </div>
        </article>
    );
}

function AddCombatantRow({
    side,
    value,
    shipKeys,
    planetKeys,
    hullKeys,
    intel,
    catalog,
    onChange,
    onAdd,
}: {
    side: SideName;
    value: CandidateKey | null;
    shipKeys: CandidateKey[];
    planetKeys: CandidateKey[];
    hullKeys: CandidateKey[];
    intel: PrivateIntelMapResponse;
    catalog: GameRuleCatalogResponse;
    onChange: (key: CandidateKey) => void;
    onAdd: () => void;
}) {
    const options = side === "left"
        ? [...shipKeys, ...hullKeys]
        : [...shipKeys, ...planetKeys, ...hullKeys];
    const current = value ?? options[0] ?? null;

    return (
        <div className="battle-sim-add-row">
            <select
                className="battle-sim-select"
                disabled={current === null}
                onChange={(event) => onChange(event.target.value as CandidateKey)}
                value={current ?? ""}
            >
                <optgroup label="Known ships">
                    {shipKeys.map((key) => (
                        <option key={key} value={key}>
                            {candidateLabel(key, intel, catalog)}
                        </option>
                    ))}
                </optgroup>
                {side === "right" && (
                    <optgroup label="Known planets / starbases">
                        {planetKeys.map((key) => (
                            <option key={key} value={key}>
                                {candidateLabel(key, intel, catalog)}
                            </option>
                        ))}
                    </optgroup>
                )}
                <optgroup label="Manual hulls">
                    {hullKeys.map((key) => (
                        <option key={key} value={key}>
                            {candidateLabel(key, intel, catalog)}
                        </option>
                    ))}
                </optgroup>
            </select>
            <button
                className="secondary-button"
                disabled={current === null}
                onClick={onAdd}
                type="button"
            >
                + {side === "left" ? "Left" : "Right"}
            </button>
        </div>
    );
}

function queueValidation(
    leftQueue: MaterializedCombatant[],
    rightQueue: MaterializedCombatant[],
): { invalid: boolean; message: string | null; fixedPlanet: boolean } {
    const leftPlanets = leftQueue.filter((item) => item.setup.kind === "planet");
    const rightPlanets = rightQueue.filter((item) => item.setup.kind === "planet");
    if (leftPlanets.length > 0) {
        return {
            invalid: true,
            message: "A planet/starbase is a fixed defender and cannot occupy the left queue.",
            fixedPlanet: false,
        };
    }
    if (rightPlanets.length > 0 && (rightQueue.length !== 1 || rightPlanets.length !== 1)) {
        return {
            invalid: true,
            message: "For planetary combat, keep exactly one fixed planet/starbase on RIGHT and queue all attacking ships on LEFT.",
            fixedPlanet: false,
        };
    }
    if (rightQueue.some((item) => item.combatant.galactic_power)) {
        return {
            invalid: true,
            message: "Galactic Power forces that Evil Empire Gorbie to LEFT. Swap sides or disable Galactic Power for this scenario.",
            fixedPlanet: false,
        };
    }
    return {
        invalid: false,
        message: null,
        fixedPlanet: rightPlanets.length === 1,
    };
}

export function BattleSimulatorWorkbench({
    game,
    intel,
    catalog,
    turn,
}: {
    game: GameDetailsResponse;
    intel: PrivateIntelMapResponse;
    catalog: GameRuleCatalogResponse;
    turn: number;
}) {
    const shipKeys = useMemo<CandidateKey[]>(
        () => intel.ships.map((ship) => `ship:${ship.ship_id}` as CandidateKey),
        [intel.ships],
    );
    const planetKeys = useMemo<CandidateKey[]>(
        () => intel.planets.map((planet) => `planet:${planet.planet_id}` as CandidateKey),
        [intel.planets],
    );
    const hullKeys = useMemo<CandidateKey[]>(
        () => catalog.hulls
            .map((hull) => intValue(hull, "id"))
            .filter((id): id is number => id !== null && id > 0)
            .map((id) => `hull:${id}` as CandidateKey),
        [catalog.hulls],
    );

    const [leftQueue, setLeftQueue] = useState<MaterializedCombatant[]>([]);
    const [rightQueue, setRightQueue] = useState<MaterializedCombatant[]>([]);
    const [selectedSide, setSelectedSide] = useState<SideName>("left");
    const [selectedLeft, setSelectedLeft] = useState(0);
    const [selectedRight, setSelectedRight] = useState(0);
    const [leftAddKey, setLeftAddKey] = useState<CandidateKey | null>(null);
    const [rightAddKey, setRightAddKey] = useState<CandidateKey | null>(null);
    const [seed, setSeed] = useState(1);
    const [battles, setBattles] = useState(10_000);
    const [rightBalanceMode, setRightBalanceMode] = useState<RightBalanceMode>("auto");
    const [running, setRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [runResult, setRunResult] = useState<BattleSimulatorRunResponse | null>(null);
    const [sequenceRun, setSequenceRun] = useState<BattleSimulatorSequenceRunResponse | null>(null);
    const [odds, setOdds] = useState<BattleSimulatorOddsResponse | null>(null);
    const [sequenceOdds, setSequenceOdds] = useState<BattleSimulatorSequenceOddsResponse | null>(null);

    function invalidateResults() {
        setRunResult(null);
        setSequenceRun(null);
        setOdds(null);
        setSequenceOdds(null);
        setError(null);
    }

    useEffect(() => {
        const observerSlot = "primary_observer" in intel
            ? intel.primary_observer.player_slot_id
            : intel.observer.player_slot_id;
        const own = intel.ships.find((ship) => ship.owner_id === observerSlot)
            ?? intel.ships[0]
            ?? null;
        const enemy = own === null
            ? intel.ships[0] ?? null
            : intel.ships.find((ship) => ship.ship_id !== own.ship_id) ?? null;

        const left = own === null
            ? (hullKeys[0] === undefined
                ? null
                : materializeCandidate(hullKeys[0], game, intel, catalog))
            : materializeCandidate(`ship:${own.ship_id}`, game, intel, catalog);

        let right = enemy === null
            ? null
            : materializeCandidate(`ship:${enemy.ship_id}`, game, intel, catalog);
        if (right === null && planetKeys[0] !== undefined) {
            right = materializeCandidate(planetKeys[0], game, intel, catalog);
        }
        if (right === null && hullKeys[0] !== undefined) {
            right = materializeCandidate(hullKeys[0], game, intel, catalog);
        }

        setLeftQueue(left === null ? [] : [left]);
        setRightQueue(right === null ? [] : [right]);
        setSelectedSide("left");
        setSelectedLeft(0);
        setSelectedRight(0);
        setLeftAddKey(shipKeys[0] ?? hullKeys[0] ?? null);
        setRightAddKey(shipKeys[0] ?? planetKeys[0] ?? hullKeys[0] ?? null);
        invalidateResults();
    }, [catalog, game, hullKeys, intel, planetKeys, shipKeys]);

    const selected = selectedSide === "left"
        ? leftQueue[selectedLeft] ?? null
        : rightQueue[selectedRight] ?? null;
    const multi = leftQueue.length > 1 || rightQueue.length > 1;
    const validation = queueValidation(leftQueue, rightQueue);

    function updateSelected(next: MaterializedCombatant) {
        if (selectedSide === "left") {
            setLeftQueue((queue) => queue.map(
                (item, index) => index === selectedLeft ? next : item,
            ));
        } else {
            setRightQueue((queue) => queue.map(
                (item, index) => index === selectedRight ? next : item,
            ));
        }
        invalidateResults();
    }

    function appendCombatant(side: SideName, next: MaterializedCombatant) {
        if (side === "left" && next.setup.kind === "planet") return;
        if (side === "left") {
            setLeftQueue((queue) => [...queue, next]);
            setSelectedLeft(leftQueue.length);
        } else {
            setRightQueue((queue) => [...queue, next]);
            setSelectedRight(rightQueue.length);
        }
        setSelectedSide(side);
        invalidateResults();
    }

    function addCombatant(side: SideName) {
        const key = side === "left"
            ? leftAddKey ?? shipKeys[0] ?? hullKeys[0] ?? null
            : rightAddKey ?? shipKeys[0] ?? planetKeys[0] ?? hullKeys[0] ?? null;
        if (key === null) return;
        const next = materializeCandidate(key, game, intel, catalog);
        if (next === null) return;
        appendCombatant(side, next);
    }

    function moveCombatant(side: SideName, index: number, delta: number) {
        const setter = side === "left" ? setLeftQueue : setRightQueue;
        setter((queue) => {
            const target = index + delta;
            if (target < 0 || target >= queue.length) return queue;
            const next = [...queue];
            [next[index], next[target]] = [next[target], next[index]];
            return next;
        });
        if (side === "left") setSelectedLeft(index + delta);
        else setSelectedRight(index + delta);
        invalidateResults();
    }

    function removeCombatant(side: SideName, index: number) {
        const setter = side === "left" ? setLeftQueue : setRightQueue;
        setter((queue) => queue.filter((_, itemIndex) => itemIndex !== index));
        if (side === "left") {
            setSelectedLeft((value) => Math.max(0, Math.min(value, leftQueue.length - 2)));
        } else {
            setSelectedRight((value) => Math.max(0, Math.min(value, rightQueue.length - 2)));
        }
        invalidateResults();
    }

    function swapSides() {
        if (rightQueue.some((item) => item.setup.kind === "planet")) return;
        if (leftQueue.some((item) => item.combatant.galactic_power)) return;
        const previousLeft = leftQueue;
        setLeftQueue(rightQueue);
        setRightQueue(previousLeft);
        setSelectedSide("left");
        setSelectedLeft(0);
        setSelectedRight(0);
        invalidateResults();
    }

    async function runOne() {
        if (
            leftQueue.length === 0
            || rightQueue.length === 0
            || validation.invalid
        ) return;
        setRunning(true);
        setError(null);
        setRunResult(null);
        setSequenceRun(null);
        try {
            if (multi) {
                setSequenceRun(await runStandaloneBattleSequence(game.game.id, {
                    left: leftQueue.map((item) => item.combatant),
                    right: rightQueue.map((item) => item.combatant),
                    seed,
                    right_balance_bonus: rightBalanceMode,
                }));
            } else {
                setRunResult(await runStandaloneBattle(game.game.id, {
                    left: leftQueue[0].combatant,
                    right: rightQueue[0].combatant,
                    seed,
                    right_balance_bonus: rightBalanceMode,
                }));
            }
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle simulation failed");
        } finally {
            setRunning(false);
        }
    }

    async function runOdds() {
        if (
            leftQueue.length === 0
            || rightQueue.length === 0
            || validation.invalid
        ) return;
        setRunning(true);
        setError(null);
        setOdds(null);
        setSequenceOdds(null);
        try {
            if (multi) {
                setSequenceOdds(await runStandaloneBattleSequenceOdds(game.game.id, {
                    left: leftQueue.map((item) => item.combatant),
                    right: rightQueue.map((item) => item.combatant),
                    battles,
                    right_balance_bonus: rightBalanceMode,
                }));
            } else {
                setOdds(await runStandaloneBattleOdds(game.game.id, {
                    left: leftQueue[0].combatant,
                    right: rightQueue[0].combatant,
                    battles,
                    right_balance_bonus: rightBalanceMode,
                }));
            }
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Battle odds failed");
        } finally {
            setRunning(false);
        }
    }

    const runDisabled = (
        running
        || leftQueue.length === 0
        || rightQueue.length === 0
        || validation.invalid
    );

    return (
        <div className="battle-sim-shell">
            <section className="battle-sim-builder">
                <header className="battle-sim-section-header">
                    <div>
                        <span className="eyebrow">BATTLE ORDER · T{turn}</span>
                        <h3>Combat queues</h3>
                        <p>
                            Add from separate Known ships, Known planets, or Generic ship / planet sources.
                            Known ships are grouped by owner race; low-armament support hulls are hidden by default.
                            For planetary waves, keep one fixed planet/starbase on RIGHT and queue attackers on LEFT.
                        </p>
                    </div>
                    <button
                        className="secondary-button"
                        disabled={
                            rightQueue.some((item) => item.setup.kind === "planet")
                            || leftQueue.some((item) => item.combatant.galactic_power)
                        }
                        onClick={swapSides}
                        type="button"
                    >
                        Swap sides
                    </button>
                </header>

                <div className="battle-sim-add-grid">
                    <BattleSimulatorAddPicker
                        catalog={catalog}
                        game={game}
                        intel={intel}
                        onAdd={(next) => appendCombatant("left", next)}
                        side="left"
                    />
                    <BattleSimulatorAddPicker
                        catalog={catalog}
                        game={game}
                        intel={intel}
                        onAdd={(next) => appendCombatant("right", next)}
                        side="right"
                    />
                </div>

                <div className="battle-sim-queues">
                    <QueueColumn
                        onMove={(index, delta) => moveCombatant("left", index, delta)}
                        onRemove={(index) => removeCombatant("left", index)}
                        onSelect={(index) => {
                            setSelectedSide("left");
                            setSelectedLeft(index);
                        }}
                        queue={leftQueue}
                        selectedIndex={selectedSide === "left" ? selectedLeft : -1}
                        side="left"
                    />
                    <QueueColumn
                        onMove={(index, delta) => moveCombatant("right", index, delta)}
                        onRemove={(index) => removeCombatant("right", index)}
                        onSelect={(index) => {
                            setSelectedSide("right");
                            setSelectedRight(index);
                        }}
                        queue={rightQueue}
                        selectedIndex={selectedSide === "right" ? selectedRight : -1}
                        side="right"
                    />
                </div>

                {validation.message !== null && (
                    <div className="battle-sim-warning">{validation.message}</div>
                )}
                {!validation.invalid && validation.fixedPlanet && multi && (
                    <div className="battle-sim-warning">
                        Fixed-defense carry-over active: planet defense, generated fighters,
                        starbase fighters, accumulated base damage, base defense/beam tech,
                        shields and derived combat mass are recomputed between waves. The
                        result is derived simulation, not a factual future state.
                    </div>
                )}
            </section>

            {selected !== null && (
                <CombatantEditor
                    catalog={catalog}
                    onChange={updateSelected}
                    value={selected}
                />
            )}

            <section className="battle-sim-controls">
                <div>
                    <span className="eyebrow">SIMULATION CONTROLS</span>
                    <h3>{multi ? "Run battle sequence" : "Run combat"}</h3>
                </div>
                <div className="battle-sim-control-row">
                    <label className="battle-sim-field battle-sim-balance-field">
                        <span>HOST right carrier balance</span>
                        <select
                            className="battle-sim-select"
                            onChange={(event) => {
                                setRightBalanceMode(event.target.value as RightBalanceMode);
                                invalidateResults();
                            }}
                            value={rightBalanceMode}
                        >
                            <option value="auto">Auto · sample HOST branch</option>
                            <option value="on">Force +360 KT when eligible</option>
                            <option value="off">Disabled</option>
                        </select>
                    </label>
                    <NumberInput
                        label="Start seed"
                        max={118}
                        min={1}
                        onChange={setSeed}
                        value={seed}
                    />
                    <button
                        className="secondary-button"
                        disabled={runDisabled}
                        onClick={() => void runOne()}
                        type="button"
                    >
                        {running
                            ? "Running…"
                            : multi
                                ? "Run sequence once"
                                : "Run visual battle"}
                    </button>
                    <NumberInput
                        label="Battles"
                        max={100000}
                        min={1}
                        onChange={setBattles}
                        value={battles}
                    />
                    <button
                        className="primary-button"
                        disabled={runDisabled}
                        onClick={() => void runOdds()}
                        type="button"
                    >
                        {running
                            ? "Simulating…"
                            : `Run ${battles.toLocaleString()} battles`}
                    </button>
                </div>
            </section>

            {error !== null && <div className="error-card">{error}</div>}

            {runResult !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">ONE BATTLE · VISUAL DERIVED SIMULATION</span>
                    {!runResult.supported ? (
                        <div className="error-card">
                            {runResult.reason ?? "Unsupported combat setup"}
                        </div>
                    ) : (
                        <CombatReplayPlayer
                            autoPlay
                            cycles={runResult.cycles}
                            frames={runResult.frames}
                            result={runResult.result}
                            title={
                                `Seed ${runResult.start_seed ?? seed}`
                                + (runResult.right_balance?.applied ? " · right +360 KT" : "")
                            }
                        />
                    )}
                </section>
            )}

            {sequenceRun !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">ONE QUEUED RUN · DERIVED SIMULATION</span>
                    {!sequenceRun.supported ? (
                        <div className="error-card">
                            {sequenceRun.reason ?? "Unsupported sequence"}
                        </div>
                    ) : (
                        <>
                            <h3>Winner: {sequenceRun.winner ?? "unknown"}</h3>
                            <div className="battle-sim-engagement-list">
                                {(sequenceRun.engagements ?? []).map((engagement) => (
                                    <div key={engagement.number}>
                                        <strong>
                                            #{engagement.number} · {leftQueue[engagement.left_index]?.combatant.name}
                                            {" vs "}
                                            {rightQueue[engagement.right_index]?.combatant.name}
                                        </strong>
                                        <span>
                                            {engagement.result.join(" + ").replaceAll("_", " ")}
                                            {` · seed ${engagement.start_seed} · ${engagement.cycles} cycles`}
                                            {engagement.right_balance_applied ? " · +360 KT right" : ""}
                                        </span>
                                        {engagement.planet_carryover !== undefined && (
                                            <small>
                                                next wave · planet DP {engagement.planet_carryover.planet_defense ?? "—"}
                                                {` · base ${engagement.planet_carryover.starbase_present ? "alive" : "gone"}`}
                                                {engagement.planet_carryover.starbase_present
                                                    ? ` · base DP ${engagement.planet_carryover.starbase_defense ?? "—"} · fighters ${engagement.planet_carryover.starbase_fighters ?? "—"} · damage ${engagement.planet_carryover.starbase_damage ?? "—"}%`
                                                    : ""}
                                            </small>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </section>
            )}

            {odds !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">REPEATED BATTLE SIMULATION</span>
                    {!odds.supported ? (
                        <div className="error-card">
                            {odds.reason ?? "Unsupported combat setup"}
                        </div>
                    ) : (
                        <>
                            <h3>{odds.sample_count.toLocaleString()} battles</h3>
                            <OutcomeGrid outcomes={odds.outcomes} />
                            {odds.sampling !== undefined && (
                                <p className="battle-sim-result-note">
                                    Right carrier balance: {odds.sampling.right_balance_mode}
                                    {` · sampled probability ${(odds.sampling.right_balance_probability * 100).toFixed(0)}% when eligible`}
                                </p>
                            )}
                            {odds.sides.left !== undefined && odds.sides.right !== undefined && (
                                <div className="battle-sim-mean-grid">
                                    <MeanSideCard
                                        label="LEFT · MEAN TERMINAL STATE"
                                        name={leftQueue[0]?.combatant.name ?? "Left"}
                                        side={odds.sides.left}
                                    />
                                    <MeanSideCard
                                        label="RIGHT · MEAN TERMINAL STATE"
                                        name={rightQueue[0]?.combatant.name ?? "Right"}
                                        side={odds.sides.right}
                                    />
                                </div>
                            )}
                        </>
                    )}
                </section>
            )}

            {sequenceOdds !== null && (
                <section className="battle-sim-result-panel">
                    <span className="eyebrow">REPEATED QUEUED SIMULATION</span>
                    {!sequenceOdds.supported ? (
                        <div className="error-card">
                            {sequenceOdds.reason ?? "Unsupported sequence"}
                        </div>
                    ) : (
                        <>
                            <h3>{sequenceOdds.sample_count.toLocaleString()} full simulations</h3>
                            <OutcomeGrid outcomes={sequenceOdds.outcomes ?? []} />
                            {sequenceOdds.sampling !== undefined && (
                                <p className="battle-sim-result-note">
                                    Right carrier balance: {sequenceOdds.sampling.right_balance_mode}
                                    {` · ${(sequenceOdds.sampling.right_balance_probability_when_eligible * 100).toFixed(0)}% when an engagement is eligible`}
                                    {` · mean ${sequenceOdds.sampling.mean_engagements} engagements`}
                                </p>
                            )}
                            {validation.fixedPlanet && (
                                <p className="battle-sim-result-note">
                                    Planet/starbase state is carried between attacker waves using the derived fixed-defense model.
                                </p>
                            )}
                            <div className="battle-sim-sequence-stats">
                                {(["left", "right"] as const).map((side) => (
                                    <div key={side}>
                                        <h4>{side.toUpperCase()} queue</h4>
                                        {(sequenceOdds.sides?.[side] ?? []).map((item) => (
                                            <article
                                                className="battle-sim-stat-card"
                                                key={item.index}
                                            >
                                                <span>
                                                    #{item.index + 1} · fought {item.fought_percent}%
                                                </span>
                                                <h4>{item.name ?? `Combatant ${item.index + 1}`}</h4>
                                                <div className="battle-sim-stat-grid">
                                                    <div><small>Avg shield</small><strong>{item.mean_final_shield ?? "—"}%</strong></div>
                                                    <div><small>Avg damage</small><strong>{item.mean_final_damage ?? "—"}%</strong></div>
                                                    <div><small>Avg crew</small><strong>{item.mean_final_crew ?? "—"}</strong></div>
                                                    <div><small>Avg torps</small><strong>{item.mean_final_torpedoes ?? "—"}</strong></div>
                                                    <div><small>Avg fighters</small><strong>{item.mean_final_fighters ?? "—"}</strong></div>
                                                </div>
                                            </article>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </section>
            )}
        </div>
    );
}
