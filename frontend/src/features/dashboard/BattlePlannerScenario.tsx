import { useEffect, useMemo, useState } from "react";

import {
    runCombatPlannerScenario,
    type CombatPlannerScenarioResponse,
    type VcrReplayTraceResponse,
} from "../../api/vcrReplay";


function parseAmmo(value: string): number | null {
    const normalized = value.trim();
    if (!/^\d+$/.test(normalized)) return null;
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}


function resultLabel(result: string[] | undefined): string {
    if (!result || result.length === 0) return "No result";
    return result.map((item) => item.split("_").join(" ")).join(", ");
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
    const factual = factualTrace.frames[0] ?? null;
    const [leftFighters, setLeftFighters] = useState("");
    const [leftTorps, setLeftTorps] = useState("");
    const [rightFighters, setRightFighters] = useState("");
    const [rightTorps, setRightTorps] = useState("");
    const [scenario, setScenario] =
        useState<CombatPlannerScenarioResponse | null>(null);
    const [running, setRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (factual === null) return;
        setLeftFighters(String(factual.left.fighters));
        setLeftTorps(String(factual.left.torpedoes));
        setRightFighters(String(factual.right.fighters));
        setRightTorps(String(factual.right.torpedoes));
        setScenario(null);
        setError(null);
    }, [vcrId, factual?.left.fighters, factual?.left.torpedoes, factual?.right.fighters, factual?.right.torpedoes]);

    const parsed = useMemo(() => ({
        leftFighters: parseAmmo(leftFighters),
        leftTorps: parseAmmo(leftTorps),
        rightFighters: parseAmmo(rightFighters),
        rightTorps: parseAmmo(rightTorps),
    }), [leftFighters, leftTorps, rightFighters, rightTorps]);

    if (factual === null || !factualTrace.supported) return null;

    const valid = Object.values(parsed).every((value) => value !== null);
    const changed = valid && (
        parsed.leftFighters !== factual.left.fighters
        || parsed.leftTorps !== factual.left.torpedoes
        || parsed.rightFighters !== factual.right.fighters
        || parsed.rightTorps !== factual.right.torpedoes
    );
    const finalFrame = scenario?.frames.at(-1) ?? null;

    async function runScenario() {
        if (!valid) return;
        setRunning(true);
        setError(null);
        try {
            const response = await runCombatPlannerScenario(
                gameId,
                linkedAccountId,
                turn,
                vcrId,
                {
                    left: {
                        fighters: parsed.leftFighters === factual.left.fighters
                            ? null
                            : parsed.leftFighters,
                        torpedoes: parsed.leftTorps === factual.left.torpedoes
                            ? null
                            : parsed.leftTorps,
                    },
                    right: {
                        fighters: parsed.rightFighters === factual.right.fighters
                            ? null
                            : parsed.rightFighters,
                        torpedoes: parsed.rightTorps === factual.right.torpedoes
                            ? null
                            : parsed.rightTorps,
                    },
                },
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

    function resetFactual() {
        setLeftFighters(String(factual.left.fighters));
        setLeftTorps(String(factual.left.torpedoes));
        setRightFighters(String(factual.right.fighters));
        setRightTorps(String(factual.right.torpedoes));
        setScenario(null);
        setError(null);
    }

    return (
        <section
            className="panel"
            style={{
                marginTop: 16,
                borderColor: "rgba(219, 166, 77, 0.45)",
                background: "rgba(33, 24, 10, 0.45)",
            }}
        >
            <div className="panel-header">
                <div>
                    <div className="eyebrow">SIMULATION · NOT STORED</div>
                    <h3 style={{ margin: "4px 0" }}>Battle Planner · VCR #{vcrId}</h3>
                    <p>
                        Starts from the factual combat-start VCR. Only the values
                        edited below are scenario assumptions; hull, equipment,
                        combat rules and RNG seed remain those of the source VCR.
                    </p>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                    <button
                        className="secondary-button"
                        disabled={running || !changed}
                        onClick={resetFactual}
                        type="button"
                    >
                        Reset factual
                    </button>
                    <button
                        className="primary-button"
                        disabled={running || !valid}
                        onClick={() => void runScenario()}
                        type="button"
                    >
                        {running ? "Simulating…" : changed ? "Run what-if" : "Replay baseline"}
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
                    ["LEFT", factual.left, leftFighters, setLeftFighters, leftTorps, setLeftTorps],
                    ["RIGHT", factual.right, rightFighters, setRightFighters, rightTorps, setRightTorps],
                ] as const).map(([label, side, fighters, setFighters, torps, setTorps]) => (
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
                                    min={0}
                                    onChange={(event) => setFighters(event.target.value)}
                                    style={{ width: "100%" }}
                                    type="number"
                                    value={fighters}
                                />
                            </label>
                            <label>
                                <small>Torpedoes · factual {side.torpedoes}</small>
                                <input
                                    min={0}
                                    onChange={(event) => setTorps(event.target.value)}
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
                    Scenario ammunition values must be non-negative integers.
                </p>
            )}
            {error !== null && (
                <div className="error-card" style={{ marginTop: 12 }}>{error}</div>
            )}

            {scenario !== null && (
                <div style={{ marginTop: 14 }}>
                    {!scenario.supported || finalFrame === null ? (
                        <div className="error-card">
                            Scenario unavailable: {scenario.reason ?? "no replay frames"}
                        </div>
                    ) : (
                        <>
                            <div className="eyebrow">SCENARIO RESULT</div>
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
                                {([finalFrame.left, finalFrame.right] as const).map((side) => (
                                    <div className="summary-card" key={`${side.object_id ?? side.name}`}>
                                        <span>{side.name ?? `Object #${side.object_id ?? "?"}`}</span>
                                        <strong>{side.damage}% damage · {side.shield}% shield</strong>
                                        <small>
                                            Crew {side.crew} · Fighters {side.fighters}
                                            {" · "}Torps {side.torpedoes}
                                        </small>
                                    </div>
                                ))}
                            </div>
                            <p style={{ marginTop: 10, color: "#cbb98f" }}>
                                Derived simulation only. No factual observation,
                                combat review state or current ship state was changed.
                            </p>
                        </>
                    )}
                </div>
            )}
        </section>
    );
}
