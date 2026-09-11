# 2026-09-11 production runtime — combat-rule reconciliation and stale-intel safety

## Source of truth

Production branch: `feature/operational-ui`

Deployed HEAD:

```text
9f40b63677e1f73a5d70f10e043ede2115d38aa1
```

Related research repository at the time of this handoff:

```text
Numillyash/planets-lab main
2cfad9f5de83e052afc420179f45ab22557cec4f
```

## What changed before this deploy

Two Battle Planner rules that had diverged from the reconstructed historical corpus were corrected and deployed in the preceding `f53e78affa21619b1f2a061438d0379fa053ebcc` production rollout:

- Federation post-combat shield recovery is `min(100 - damage, shield + 25)`, not 25% of missing shields.
- Native planet beam tech uses nearest-integer `ROUND(SQRT(DP / 2))`, not truncating/floor square-root behavior.

The independent `planets-lab` cross-repo regression gate checked immutable downloaded `loadall` games rather than the production database:

- Federation: corrected formula 48/48 comparable race-1 transitions; old IntelBoard formula 38/48; 10 corrected-only discriminators; 0 old-only.
- Native planet beam tech: corrected formula 1036/1036 ordinary Classic cases; old truncating formula 712/1036; 324 corrected-only discriminators; 0 old-only.

Evidence boundary: these are historical corpus results, not claims inferred from current production behavior.

The same `f53e78a` rollout also hardened private refresh handling: a HTTP-200 refresh response whose accessible private observers all failed is surfaced as an actionable frontend warning instead of being silently treated as success.

## Stale private-intel fail-closed behavior

PR #4 (`fix: fail closed on stale private intel`) was merged to `feature/operational-ui` as:

```text
9f40b63677e1f73a5d70f10e043ede2115d38aa1
```

`DashboardApp` now compares the canonical game turn with the factual private snapshot turn.

When `privateIntel.turn !== game.game.turn`:

- the current-turn `GameDashboard` receives no private factual snapshot;
- stale private facts therefore cannot be relabelled as the canonical current turn in current fact tables;
- an explicit amber warning displays both turns;
- the map remains available because its own header identifies the factual snapshot turn explicitly.

This is a fail-closed provenance rule. It does not mutate or reinterpret the stored observation.

PR CI passed backend tests, frontend type-check/build, and production-image build before merge. The merge commit was also exercised by branch CI.

## Production deployment evidence

Server command used the versioned production deployment script.

Observed runtime result:

```text
HEAD: 9f40b63677e1f73a5d70f10e043ede2115d38aa1
Build: OK
Backend tests: OK
Ran 289 tests in 0.222s
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after:  0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
Log: /opt/planets-intel/logs/deploy/20260911-211534-production.log
DEPLOY OK
```

Therefore the following are deployed in production as of this checkpoint:

1. corpus-reconciled Federation recovery;
2. corpus-reconciled native planet beam-tech rounding;
3. total private-refresh failure surfacing;
4. current-dashboard fail-closed behavior for a stale private snapshot.

Browser acceptance of an intentionally reproduced stale-turn mismatch warning is not separately recorded yet. The server/runtime deployment is successful; a future browser check should be treated as UI acceptance only, not as a prerequisite for the backend/runtime checkpoint above.

## Movement research reconciliation

The adjacent `planets-lab` research has advanced beyond older IntelBoard handoffs.

Base finite-fuel Tow movement semantics in ordinary Classic/Nu scope are now supported as:

- documented by official Nu fuel/Host-order material;
- observed in the historical corpus;
- tested;
- differential-verified.

The cleaned T41 historical discriminator selects post-Alchemy combined tower+towed mass with proportional insufficient-fuel movement over both pre-Alchemy combined mass and post-Alchemy tower-only mass.

This does **not** mean every old production finite-fuel Tow guard can be removed automatically. IntelBoard still must distinguish rule knowledge from availability of the actual Tow-phase fuel state. Snapshot neutronium must not be silently promoted to movement-phase neutronium.

Unrelated Tow interactions such as web-hit RNG/location, contests/chains/cycles, and other special phase interactions remain separately scoped.

## Product direction after this checkpoint

The unified movement pipeline already exists in IntelBoard: Tow, Move Most and Intercept are represented through the shared movement-turn state and draft movement-prediction endpoint. The next product work should build on that implementation rather than reconstructing another movement pipeline.

Immediate product priorities:

1. Turn Review / provenance UI that keeps FACTUAL, local DRAFT, PREDICTED and UNKNOWN state visibly separate.
2. Reconcile remaining production movement fail-closed reasons with current `planets-lab` evidence, without crossing the phase-state data boundary.
3. Browser acceptance for explicit Tow target save/precedence and `PREDICTED TOW` / `PREDICTED TOWED` rendering.
4. Continue operational sync diagnostics only when a concrete regression appears; the proxy incident itself is considered resolved.

Research continues independently in `planets-lab`, with Host combat ordering/engagement orchestration now a higher-value reverse-engineering target than reopening ordinary movement without a bounded contradiction.
