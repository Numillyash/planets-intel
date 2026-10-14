import { useEffect, useMemo, useState } from "react";

import {
    runCombatPlannerOdds,
    runCombatPlannerRepeatOdds,
    runCombatPlannerScenario,
    type CombatPlannerOddsResponse,
    type CombatPlannerScenarioRequest,
    type CombatPlannerScenarioResponse,
    type VcrReplaySideFrame,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";

function parseAmmo(value: string): number | null {
    const normalized = value.trim();
    if (!/^\d+$/.test(normalized)) return null;
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) && parsed >= 0 && parsed <= 100_000
        ? parsed
        : null;
}

function parseBattles(value: string): number | null {
    const normalized = value.trim();
    if (!/^\d+$/.test(normalized)) return null;
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) && parsed >= 1 && parsed <= 100_000
        ? parsed
        : null;
}

function resultLabel(result: string[] | undefined): string {
    if (!result || result.length === 0) return "No terminal result";
    return result.map((item) => item.split("_").join(" ")).join(", ");
}

function outcomeLabel(outcome: string): string {
    return outcome.split("+").map((item) => item.split("_").join(" ")).join(" + ");
}

function terminalLabel(side: VcrReplaySideFrame): string {
    if (side.damage >= 100 || side.crew <= 0) return "destroyed";
    return "survived";
}

function TerminalState({
    title,
    side,
}: {
    title: string;
    side: VcrReplaySideFrame;
}) {
    return (
        <article className="battle-sim-stat-card">
            <span>{title} · TERMINAL STATE</span>
            <h4>{side.name ?? `Object #${side.object_id ?? "?"}`}</h4>
            <div className="battle-sim-stat-grid">
                <div><small>Result</small><strong>{terminalLabel(side)}</strong></div>
                <div><small>Shield</small><strong>{side.shield}%</strong></div>
                <div><small>Damage</small><strong>{side.damage}%</strong></div>
                <div><small>Crew</small><strong>{side.crew}</strong></div>
                <div><small>Torps left</small><strong>{side.torpedoes}</strong></div>
                <div><small>Fighters left</small><strong>{side.fighters}</strong></div>
            </div>
        </article>
    );
}

function effectiveStartAmmo(
    result: CombatPlannerOddsResponse,
    sideName: "left" | "right",
    key: "fighters" | "torpedoes",
): number | null {
    const assumed = result.assumptions[sideName]?.[key];
    if (typeof assumed === "number" && Number.isFinite(assumed)) return assumed;
    const baseline = result.baseline[sideName]?.[key];
    return typeof baseline === "number" && Number.isFinite(baseline)
        ? baseline
        : null;
}

function meanSpent(start: number | null, finalValue: number): string {
    if (start === null) return "—";
    return Math.max(0, start - finalValue).toFixed(2).replace(/\.00$/, "");
}

function PlannerMeanSideCard({
    label,
    source,
    side,
    result,
    sideName,
}: {
    label: string;
    source: VcrReplaySideFrame;
    side: NonNullable<CombatPlannerOddsResponse["sides"]["left"]>;
    result: CombatPlannerOddsResponse;
    sideName: "left" | "right";
}) {
    const startTorps = effectiveStartAmmo(result, sideName, "torpedoes");
    const startFighters = effectiveStartAmmo(result, sideName, "fighters");

    return (
        <article className="battle-sim-stat-card">
            <span>{label}</span>
            <h4>{source.name ?? `#${source.object_id ?? "?"}`}</h4>
            <div className="battle-sim-stat-grid">
                <div>
                    <small>Survival</small>
                    <strong>{side.survival_seed_frequency_percent}%</strong>
                </div>
                <div><small>Avg shield</small><strong>{side.mean_final_shield}%</strong></div>
                <div><small>Avg damage</small><strong>{side.mean_final_damage}%</strong></div>
                <div><small>Avg crew</small><strong>{side.mean_final_crew}</strong></div>
                <div><small>Avg torps left</small><strong>{side.mean_final_torpedoes}</strong></div>
                <div><small>Avg torps fired</small><strong>{meanSpent(startTorps, side.mean_final_torpedoes)}</strong></div>
                <div><small>Avg fighters left</small><strong>{side.mean_final_fighters}</strong></div>
                <div><small>Avg fighters lost</small><strong>{meanSpent(startFighters, side.mean_final_fighters)}</strong></div>
            </div>
            <small>
                survived {side.survived_count} · destroyed {side.destroyed_count}
                {side.captured_count > 0 ? ` · captured ${side.captured_count}` : ""}
            </small>
        </article>
    );
}

function OddsResultPanel({
    result,
    factualStart,
    mode,
}: {
    result: CombatPlannerOddsResponse;
    factualStart: VcrReplayTraceResponse["frames"][number];
    mode: "repeat" | "series";
}) {
    const repeat = mode === "repeat";
    return (
        <section className="battle-sim-result-panel">
            {!result.supported ? (
                <div className="error-card">
                    Simulation unavailable: {result.reason ?? "unsupported combat mode"}
                </div>
            ) : (
                <>
                    <div className="eyebrow">
                        {repeat
                            ? "REPEATED BATTLE SAMPLE · DERIVED SIMULATION"
                            : "FULL CLASSIC SEED SERIES · DERIVED SIMULATION"}
                    </div>
                    <h3>
                        {result.sample_count.toLocaleString()} {repeat ? "battles simulated" : "start seeds evaluated"}
                    </h3>

                    {result.sides.left !== undefined && result.sides.right !== undefined && (
                        <div className="battle-sim-mean-grid">
                            <PlannerMeanSideCard
                                label="LEFT · MEAN TERMINAL STATE"
                                result={result}
                                side={result.sides.left}
                                sideName="left"
                                source={factualStart.left}
                            />
                            <PlannerMeanSideCard
                                label="RIGHT · MEAN TERMINAL STATE"
                                result={result}
                                side={result.sides.right}
                                sideName="right"
                                source={factualStart.right}
                            />
                        </div>
                    )}

                    <div className="table-wrapper" style={{ marginTop: 14 }}>
                        <table className="players-table game-object-table">
                            <thead>
                                <tr>
                                    <th>Outcome</th>
                                    <th>{repeat ? "Battles" : "Seeds"}</th>
                                    <th>Frequency</th>
                                    <th>Example seed</th>
                                </tr>
                            </thead>
                            <tbody>
                                {result.outcomes.map((outcome) => (
                                    <tr key={outcome.outcome}>
                                        <td className="player-name">{outcomeLabel(outcome.outcome)}</td>
                                        <td>{outcome.count}</td>
                                        <td>{outcome.seed_frequency_percent}%</td>
                                        <td>{outcome.representative_seed ?? "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <p className="battle-sim-result-note">
                        {repeat
                            ? "Repeated mode samples Classic combat start seeds with replacement. Torps fired are start minus terminal torpedoes. Fighters lost are start minus terminal fighters after surviving launched fighters have been returned by the deterministic engine. Results are simulation only and are never persisted as factual intel."
                            : "Series mode evaluates every documented Classic start seed exactly once. It is useful for deterministic engine validation and has no sampling noise."}
                    </p>
                </>
            )}
        </section>
    );
}

export function BattlePlannerScenario({
    gameId,
    linkedAccountId,
    turn,
    vcrId,
    factualTrace,
}: {
    gameId: number;
    linkedAccountId: number;
    turn: number;
    vcrId: number;
    factualTrace: VcrReplayTraceResponse;
}) {
    const factualStart = factualTrace.frames[0] ?? null;
    const factualEnd = factualTrace.frames.length > 0
        ? factualTrace.frames[factualTrace.frames.length - 1]
        : null;
    const [leftFighters, setLeftFighters] = useState("");
    const [leftTorps, setLeftTorps] = useState("");
    const [rightFighters, setRightFighters] = useState("");
    const [rightTorps, setRightTorps] = useState("");
    const [battleCount, setBattleCount] = useState("10000");
    const [scenario, setScenario] = useState<CombatPlannerScenarioResponse | null>(null);
    const [odds, setOdds] = useState<CombatPlannerOddsResponse | null>(null);
    const [series, setSeries] = useState<CombatPlannerOddsResponse | null>(null);
    const [running, setRunning] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [seriesRunning, setSeriesRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (factualStart === null) return;
        setLeftFighters(String(factualStart.left.fighters));
        setLeftTorps(String(factualStart.left.torpedoes));
        setRightFighters(String(factualStart.right.fighters));
        setRightTorps(String(factualStart.right.torpedoes));
        setScenario(null);
        setOdds(null);
        setSeries(null);
        setError(null);
    }, [
        vcrId,
        factualStart?.left.fighters,
        factualStart?.left.torpedoes,
        factualStart?.right.fighters,
        factualStart?.right.torpedoes,
    ]);

    const parsed = useMemo(() => ({
        leftFighters: parseAmmo(leftFighters),
        leftTorps: parseAmmo(leftTorps),
        rightFighters: parseAmmo(rightFighters),
        rightTorps: parseAmmo(rightTorps),
        battles: parseBattles(battleCount),
    }), [battleCount, leftFighters, leftTorps, rightFighters, rightTorps]);

    if (factualStart === null || !factualTrace.supported) return null;

    const validAmmo = [
        parsed.leftFighters,
        parsed.leftTorps,
        parsed.rightFighters,
        parsed.rightTorps,
    ].every((value) => value !== null);
    const valid = validAmmo && parsed.battles !== null;
    const changed = validAmmo && (
        parsed.leftFighters !== factualStart.left.fighters
        || parsed.leftTorps !== factualStart.left.torpedoes
        || parsed.rightFighters !== factualStart.right.fighters
        || parsed.rightTorps !== factualStart.right.torpedoes
    );
    const scenarioFinal = scenario !== null && scenario.frames.length > 0
        ? scenario.frames[scenario.frames.length - 1]
        : null;

    function requestBody(): CombatPlannerScenarioRequest | null {
        if (!validAmmo) return null;
        return {
            left: {
                fighters: parsed.leftFighters === factualStart.left.fighters
                    ? null
                    : parsed.leftFighters,
                torpedoes: parsed.leftTorps === factualStart.left.torpedoes
                    ? null
                    : parsed.leftTorps,
            },
            right: {
                fighters: parsed.rightFighters === factualStart.right.fighters
                    ? null
                    : parsed.rightFighters,
                torpedoes: parsed.rightTorps === factualStart.right.torpedoes
                    ? null
                    : parsed.rightTorps,
            },
        };
    }

    function invalidateResults() {
        setScenario(null);
        setOdds(null);
        setSeries(null);
        setError(null);
    }

    async function runScenario() {
        const request = requestBody();
        if (request === null) return;
        setRunning(true);
        setError(null);
        try {
            setScenario(await runCombatPlannerScenario(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                request,
            ));
        } catch (reason) {
            setScenario(null);
            setError(reason instanceof Error ? reason.message : "Battle planner scenario failed");
        } finally {
            setRunning(false);
        }
    }

    async function analyzeOdds() {
        const request = requestBody();
        if (request === null || parsed.battles === null) return;
        setAnalyzing(true);
        setError(null);
        try {
            setOdds(await runCombatPlannerRepeatOdds(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                {
                    ...request,
                    battles: parsed.battles,
                    sampling_seed: null,
                },
            ));
        } catch (reason) {
            setOdds(null);
            setError(reason instanceof Error ? reason.message : "Repeated battle simulation failed");
        } finally {
            setAnalyzing(false);
        }
    }

    async function runFullSeries() {
        const request = requestBody();
        if (request === null) return;
        setSeriesRunning(true);
        setError(null);
        try {
            setSeries(await runCombatPlannerOdds(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                request,
            ));
        } catch (reason) {
            setSeries(null);
            setError(reason instanceof Error ? reason.message : "Full Classic seed series failed");
        } finally {
            setSeriesRunning(false);
        }
    }

    function resetFactual() {
        setLeftFighters(String(factualStart.left.fighters));
        setLeftTorps(String(factualStart.left.torpedoes));
        setRightFighters(String(factualStart.right.fighters));
        setRightTorps(String(factualStart.right.torpedoes));
        invalidateResults();
    }

    const busy = running || analyzing || seriesRunning;

    return (
        <div className="game-dashboard-stack">
            <section
                className="panel"
                style={{
                    borderColor: "rgba(219, 166, 77, 0.45)",
                    background: "rgba(33, 24, 10, 0.45)",
                }}
            >
                <div className="panel-header">
                    <div>
                        <div className="eyebrow">SIMULATION · NOT STORED</div>
                        <h3 style={{ margin: "4px 0" }}>Scenario assumptions</h3>
                        <p>
                            The source VCR remains factual and unchanged. Only fighters
                            and torpedoes edited below are replaced for this replay setup;
                            hull, weapons, race and combat rules stay factual.
                        </p>
                    </div>
                    <div className="battle-sim-control-row">
                        <label className="battle-sim-field" style={{ width: 120 }}>
                            <span>Battles</span>
                            <input
                                className="battle-sim-input"
                                max={100000}
                                min={1}
                                onChange={(event) => {
                                    setBattleCount(event.target.value);
                                    invalidateResults();
                                }}
                                type="number"
                                value={battleCount}
                            />
                        </label>
                        <button
                            className="secondary-button"
                            disabled={busy || !changed}
                            onClick={resetFactual}
                            type="button"
                        >
                            Reset factual
                        </button>
                        <button
                            className="secondary-button"
                            disabled={busy || !validAmmo}
                            onClick={() => void runFullSeries()}
                            type="button"
                        >
                            {seriesRunning ? "Running series…" : "Full 118-seed series"}
                        </button>
                        <button
                            className="secondary-button"
                            disabled={busy || !validAmmo}
                            onClick={() => void runScenario()}
                            type="button"
                        >
                            {running
                                ? "Simulating…"
                                : changed
                                    ? "Run source-seed what-if"
                                    : "Replay source seed"}
                        </button>
                        <button
                            className="primary-button"
                            disabled={busy || !valid}
                            onClick={() => void analyzeOdds()}
                            type="button"
                        >
                            {analyzing
                                ? "Running battles…"
                                : `Run ${(parsed.battles ?? 0).toLocaleString()} battles`}
                        </button>
                    </div>
                </div>

                <div className="battle-sim-mean-grid">
                    {([
                        [
                            "LEFT",
                            factualStart.left,
                            leftFighters,
                            setLeftFighters,
                            leftTorps,
                            setLeftTorps,
                        ],
                        [
                            "RIGHT",
                            factualStart.right,
                            rightFighters,
                            setRightFighters,
                            rightTorps,
                            setRightTorps,
                        ],
                    ] as const).map(([
                        label,
                        side,
                        fighters,
                        setFighters,
                        torps,
                        setTorps,
                    ]) => (
                        <article className="battle-sim-stat-card" key={label}>
                            <span>{label}</span>
                            <h4>{side.name ?? `#${side.object_id ?? "?"}`}</h4>
                            <div className="battle-sim-fields battle-sim-fields-3">
                                <label className="battle-sim-field">
                                    <span>Fighters · factual {side.fighters}</span>
                                    <input
                                        className="battle-sim-input"
                                        max={100000}
                                        min={0}
                                        onChange={(event) => {
                                            setFighters(event.target.value);
                                            invalidateResults();
                                        }}
                                        type="number"
                                        value={fighters}
                                    />
                                </label>
                                <label className="battle-sim-field">
                                    <span>Torpedoes · factual {side.torpedoes}</span>
                                    <input
                                        className="battle-sim-input"
                                        max={100000}
                                        min={0}
                                        onChange={(event) => {
                                            setTorps(event.target.value);
                                            invalidateResults();
                                        }}
                                        type="number"
                                        value={torps}
                                    />
                                </label>
                            </div>
                        </article>
                    ))}
                </div>

                {!validAmmo && (
                    <p className="battle-sim-warning">
                        Scenario ammo values must be integers from 0 to 100000.
                    </p>
                )}
                {parsed.battles === null && (
                    <p className="battle-sim-warning">
                        Battle count must be an integer from 1 to 100000.
                    </p>
                )}
                {error !== null && <div className="error-card">{error}</div>}
            </section>

            {odds !== null && (
                <OddsResultPanel factualStart={factualStart} mode="repeat" result={odds} />
            )}

            {series !== null && (
                <OddsResultPanel factualStart={factualStart} mode="series" result={series} />
            )}

            {factualEnd !== null && (
                <section className="battle-sim-result-panel">
                    <div className="eyebrow">FACTUAL VCR SEED · DETERMINISTIC BASELINE</div>
                    <h3>
                        {resultLabel(factualTrace.result)} · {factualTrace.cycles ?? 0} cycles
                    </h3>
                    <div className="battle-sim-mean-grid">
                        <TerminalState title="LEFT" side={factualEnd.left} />
                        <TerminalState title="RIGHT" side={factualEnd.right} />
                    </div>
                    <p className="battle-sim-result-note">
                        This terminal state is derived by deterministic replay from the
                        factual VCR seed. It is not written back as a current ship fact.
                    </p>
                </section>
            )}

            {scenario !== null && (
                <section className="battle-sim-result-panel">
                    {!scenario.supported || scenarioFinal === null ? (
                        <div className="error-card">
                            Scenario unavailable: {scenario.reason ?? "no replay frames"}
                        </div>
                    ) : (
                        <>
                            <div className="eyebrow">SOURCE-SEED RESULT · DERIVED SIMULATION</div>
                            <h3>
                                {resultLabel(scenario.result)} · {scenario.cycles ?? 0} cycles
                            </h3>
                            <div className="battle-sim-mean-grid">
                                <TerminalState title="LEFT" side={scenarioFinal.left} />
                                <TerminalState title="RIGHT" side={scenarioFinal.right} />
                            </div>
                            <p className="battle-sim-result-note">
                                Simulation only · persisted=false · source basis=factual VCR.
                                No observation, analyst review or current ship state changed.
                            </p>
                        </>
                    )}
                </section>
            )}
        </div>
    );
}
