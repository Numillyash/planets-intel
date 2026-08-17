import { useEffect, useMemo, useState } from "react";

import {
    runCombatPlannerOdds,
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
        <div className="summary-card">
            <span>{title} · {side.name ?? `Object #${side.object_id ?? "?"}`}</span>
            <strong>
                {terminalLabel(side)} · {side.damage}% damage · {side.shield}% shield
            </strong>
            <small>
                Crew {side.crew} · Fighters {side.fighters} · Torps {side.torpedoes}
            </small>
        </div>
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
    const [scenario, setScenario] =
        useState<CombatPlannerScenarioResponse | null>(null);
    const [odds, setOdds] = useState<CombatPlannerOddsResponse | null>(null);
    const [running, setRunning] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (factualStart === null) return;
        setLeftFighters(String(factualStart.left.fighters));
        setLeftTorps(String(factualStart.left.torpedoes));
        setRightFighters(String(factualStart.right.fighters));
        setRightTorps(String(factualStart.right.torpedoes));
        setScenario(null);
        setOdds(null);
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
    }), [leftFighters, leftTorps, rightFighters, rightTorps]);

    if (factualStart === null || !factualTrace.supported) return null;

    const valid = Object.values(parsed).every((value) => value !== null);
    const changed = valid && (
        parsed.leftFighters !== factualStart.left.fighters
        || parsed.leftTorps !== factualStart.left.torpedoes
        || parsed.rightFighters !== factualStart.right.fighters
        || parsed.rightTorps !== factualStart.right.torpedoes
    );
    const scenarioFinal = scenario !== null && scenario.frames.length > 0
        ? scenario.frames[scenario.frames.length - 1]
        : null;

    function requestBody(): CombatPlannerScenarioRequest | null {
        if (!valid) return null;
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
        setError(null);
    }

    async function runScenario() {
        const request = requestBody();
        if (request === null) return;
        setRunning(true);
        setError(null);
        try {
            const response = await runCombatPlannerScenario(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                request,
            );
            setScenario(response);
        } catch (reason) {
            setScenario(null);
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Battle planner scenario failed",
            );
        } finally {
            setRunning(false);
        }
    }

    async function analyzeOdds() {
        const request = requestBody();
        if (request === null) return;
        setAnalyzing(true);
        setError(null);
        try {
            const response = await runCombatPlannerOdds(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                request,
            );
            setOdds(response);
        } catch (reason) {
            setOdds(null);
            setError(
                reason instanceof Error
                    ? reason.message
                    : "Battle seed sweep failed",
            );
        } finally {
            setAnalyzing(false);
        }
    }

    function resetFactual() {
        setLeftFighters(String(factualStart.left.fighters));
        setLeftTorps(String(factualStart.left.torpedoes));
        setRightFighters(String(factualStart.right.fighters));
        setRightTorps(String(factualStart.right.torpedoes));
        setScenario(null);
        setOdds(null);
        setError(null);
    }

    return (
        <div style={{ display: "grid", gap: 14 }}>
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
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                            className="secondary-button"
                            disabled={running || analyzing || !changed}
                            onClick={resetFactual}
                            type="button"
                        >
                            Reset factual
                        </button>
                        <button
                            className="secondary-button"
                            disabled={running || analyzing || !valid}
                            onClick={() => void analyzeOdds()}
                            type="button"
                        >
                            {analyzing ? "Sweeping seeds…" : "Analyze all 118 seeds"}
                        </button>
                        <button
                            className="primary-button"
                            disabled={running || analyzing || !valid}
                            onClick={() => void runScenario()}
                            type="button"
                        >
                            {running
                                ? "Simulating…"
                                : changed
                                    ? "Run source-seed what-if"
                                    : "Replay source seed"}
                        </button>
                    </div>
                </div>

                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                        gap: 14,
                    }}
                >
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
                        <div className="summary-card" key={label}>
                            <span>{label} · {side.name ?? `#${side.object_id ?? "?"}`}</span>
                            <div
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                                    gap: 10,
                                    marginTop: 9,
                                }}
                            >
                                <label>
                                    <small>Fighters · factual {side.fighters}</small>
                                    <input
                                        max={100000}
                                        min={0}
                                        onChange={(event) => {
                                            setFighters(event.target.value);
                                            invalidateResults();
                                        }}
                                        style={{ width: "100%" }}
                                        type="number"
                                        value={fighters}
                                    />
                                </label>
                                <label>
                                    <small>Torpedoes · factual {side.torpedoes}</small>
                                    <input
                                        max={100000}
                                        min={0}
                                        onChange={(event) => {
                                            setTorps(event.target.value);
                                            invalidateResults();
                                        }}
                                        style={{ width: "100%" }}
                                        type="number"
                                        value={torps}
                                    />
                                </label>
                            </div>
                        </div>
                    ))}
                </div>

                {!valid && (
                    <p style={{ color: "#e0a7a7", marginTop: 12 }}>
                        Scenario ammo values must be integers from 0 to 100000.
                    </p>
                )}
                {error !== null && (
                    <div className="error-card" style={{ marginTop: 12 }}>{error}</div>
                )}
            </section>

            {odds !== null && (
                <section
                    className="panel"
                    style={{ borderColor: "rgba(117, 177, 227, 0.55)" }}
                >
                    {!odds.supported ? (
                        <div className="error-card">
                            Seed sweep unavailable: {odds.reason ?? "unsupported combat mode"}
                        </div>
                    ) : (
                        <>
                            <div className="eyebrow">EXHAUSTIVE CLASSIC SEED SWEEP</div>
                            <h3 style={{ margin: "4px 0 10px" }}>
                                {odds.sample_count} documented start seeds evaluated
                            </h3>

                            <div
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                                    gap: 14,
                                    marginBottom: 14,
                                }}
                            >
                                {(["left", "right"] as const).map((sideName) => {
                                    const side = odds.sides[sideName];
                                    if (side === undefined) return null;
                                    const source = sideName === "left"
                                        ? factualStart.left
                                        : factualStart.right;
                                    return (
                                        <div className="summary-card" key={sideName}>
                                            <span>
                                                {sideName.toUpperCase()} · {source.name ?? `#${source.object_id ?? "?"}`}
                                            </span>
                                            <strong>
                                                Survival seed frequency {side.survival_seed_frequency_percent}%
                                            </strong>
                                            <small>
                                                survived {side.survived_count} · destroyed {side.destroyed_count}
                                                {side.captured_count > 0 ? ` · captured ${side.captured_count}` : ""}
                                            </small>
                                            <small>
                                                mean final: {side.mean_final_damage}% damage · {side.mean_final_shield}% shield
                                                {" · "}crew {side.mean_final_crew}
                                                {" · "}torps {side.mean_final_torpedoes}
                                                {" · "}fighters {side.mean_final_fighters}
                                            </small>
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="table-wrapper">
                                <table className="players-table game-object-table">
                                    <thead>
                                        <tr>
                                            <th>Outcome</th>
                                            <th>Seeds</th>
                                            <th>Frequency</th>
                                            <th>Example seed</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {odds.outcomes.map((outcome) => (
                                            <tr key={outcome.outcome}>
                                                <td className="player-name">
                                                    {outcomeLabel(outcome.outcome)}
                                                </td>
                                                <td>{outcome.count}</td>
                                                <td>{outcome.seed_frequency_percent}%</td>
                                                <td>{outcome.representative_seed ?? "—"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            <p style={{ marginTop: 10, color: "#91a9c8" }}>
                                This is an exhaustive frequency over the 118 documented
                                Classic start seeds, not a claim that Host selects those
                                seeds uniformly. It has no Monte Carlo sampling noise and
                                is never persisted as factual intel.
                            </p>
                        </>
                    )}
                </section>
            )}

            {factualEnd !== null && (
                <section className="panel">
                    <div className="eyebrow">FACTUAL VCR SEED · DETERMINISTIC BASELINE</div>
                    <h3 style={{ margin: "4px 0 10px" }}>
                        {resultLabel(factualTrace.result)} · {factualTrace.cycles ?? 0} cycles
                    </h3>
                    <div
                        style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                            gap: 14,
                        }}
                    >
                        <TerminalState title="LEFT" side={factualEnd.left} />
                        <TerminalState title="RIGHT" side={factualEnd.right} />
                    </div>
                    <p style={{ marginTop: 10, color: "#91a9c8" }}>
                        This terminal state is derived by deterministic replay from the
                        factual VCR seed. It is not written back as a current ship fact.
                    </p>
                </section>
            )}

            {scenario !== null && (
                <section
                    className="panel"
                    style={{ borderColor: "rgba(219, 166, 77, 0.55)" }}
                >
                    {!scenario.supported || scenarioFinal === null ? (
                        <div className="error-card">
                            Scenario unavailable: {scenario.reason ?? "no replay frames"}
                        </div>
                    ) : (
                        <>
                            <div className="eyebrow">SOURCE-SEED RESULT · DERIVED SIMULATION</div>
                            <h3 style={{ margin: "4px 0 10px" }}>
                                {resultLabel(scenario.result)} · {scenario.cycles ?? 0} cycles
                            </h3>
                            <div
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                                    gap: 14,
                                }}
                            >
                                <TerminalState title="LEFT" side={scenarioFinal.left} />
                                <TerminalState title="RIGHT" side={scenarioFinal.right} />
                            </div>
                            <p style={{ marginTop: 10, color: "#cbb98f" }}>
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
