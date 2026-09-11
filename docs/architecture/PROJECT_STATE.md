# Planets Intel — Project State

This is the durable architectural state for `Numillyash/planets-intel`. Git history is the detailed implementation log. For the exact latest runtime/deploy checkpoint, also read `docs/architecture/CURRENT_HANDOFF.md` and the newest dated file under `docs/handoff/`.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, historical evidence, explicit read-time inference, local order drafting, bounded simulation/prediction and eventually reviewed upstream turn submission.
- UI direction: Planets-style operational dashboard + Pixi starmap; facts and provenance stay first-class.
- Source of truth across chats: GitHub repository and durable handoff docs. Never reconstruct current implementation from chat memory.
- Current product focus: provenance-safe Turn Review and reconciliation of proven `planets-lab` mechanics into the existing prediction/Battle Planner stack.
- Current research focus is separate: `planets-lab` continues Host combat ordering/orchestration and other unresolved Host mechanics.

## Production checkpoint

On 2026-09-11 production was successfully deployed at:

```text
f5c9ab9bfcc3c9c5bb32f2bbf7a5f0f3340e0ced
```

with 296 backend tests passing, DB head `0018_tow_target_ship_id`, successful backend recreation and healthy `/api/health`.

This checkpoint includes:

- corpus-reconciled Federation shield recovery;
- corpus-reconciled native planet beam-tech rounding;
- total private-refresh failure surfacing;
- fail-closed current dashboard behavior when the factual private snapshot turn differs from the canonical game turn;
- the first production Turn Review / evidence ledger using the existing unified movement prediction stack;
- structured provenance for UNKNOWN movement rows, distinguishing unavailable phase-state, implementation gaps, missing facts, unresolved dependencies, order ambiguity and unsupported Host rules;
- lab-verified true-partial normal-speed Move Most fuel semantics with Host major/minor-axis endpoint projection and continuous nominal one-turn fuel basis.

Detailed runtime records:

- `docs/handoff/2026-09-11-turn-review-blockers-production.md`
- `docs/handoff/2026-09-12-true-partial-move-most-production.md`

## Stable baseline

- Linked Planets.nu accounts and game-centric chooser with deep-linked `/intelboard/<observer>/<game>` routes.
- Automatic discovery/private refresh for active games.
- Public `loadinfo` / `loadscores` ingestion, score history, scoreboard and activity tracking.
- Private `loadturn` ingestion and combined multi-account intel with provenance.
- Fullscreen Pixi starmap with operational entity panes and cached Planets.nu hull/planet artwork.
- Historical private snapshots and Time Machine / historical mode.
- Historical ship tracks with lifecycle splitting for reused numeric ship IDs.
- VCR ingestion, combat evidence and Battle Planner infrastructure.
- Threat analysis and military attribution/read-time inference layers.
- Communications with accepted private grouping / race-first display behavior.
- Local ship, planet and starbase order drafts.
- Unified movement-turn state and movement prediction across Tow, Move Most and Intercept.
- Explicit Tow target draft field and related prediction plumbing.
- Provenance-safe Turn Review separating current facts, prediction and UNKNOWN output.
- Structured blocker provenance for uncertain movement output.
- Verified true-partial normal-speed Move Most projection/fuel semantics.
- Production deployment script with build/test/migration/health gates.

## Evidence architecture

The product must preserve these separations:

```text
factual observation
    != historical observation merely because an ID matches
    != analyst confirmation
    != inference
    != local order draft
    != simulation / prediction
```

Additional invariants:

- known zero != unknown;
- missing != zero;
- current fact != historical fact;
- combat-time evidence != current object state;
- hull capacity != factual current weapons;
- snapshot neutronium != automatically movement-phase neutronium;
- unsupported Host behavior fails closed.

Combined intel is a factual aggregation layer. It may select the freshest known factual value per field while retaining source provenance; it must not silently turn inference or prediction into facts.

## Movement state

The unified movement implementation is already present; do not create a parallel prediction subsystem.

Core concepts/files include:

- `movement_turn_state.py`
- `movement_prediction.py`
- `movement_prediction_runtime.py`
- `movement_prediction_unified_runtime.py`
- `movement_prediction_blockers.py`
- `movement_tow.py`
- `movement_move_most.py`
- `movement_intercept.py`
- `movement_fuel.py` / `movement_fuel_policy.py`
- frontend movement-prediction API/hook/state and order-vector scenes.

The response contract explicitly marks movement output as derived and `host_final: false`.

UNKNOWN movement output must preserve the reason boundary. The product distinguishes a missing phase-state input, a missing factual field, an unresolved dependency/order ambiguity, a lab-verified rule that has not yet been integrated safely, and a genuinely unsupported Host rule. This classification is provenance metadata only; it must never increase endpoint certainty by itself.

The deployed blocker classes are:

```text
phase_state_required
implementation_gap
missing_fact
dependency_unresolved
order_ambiguity
unsupported_host_rule
```

### Research status imported from planets-lab

Ordinary Classic movement is now a comparatively mature research area. Historical differential work has supported true-partial normal movement geometry/fuel semantics and base finite-fuel Tow movement.

Base finite-fuel Tow movement is supported in `planets-lab` as:

`DOCUMENTED + CORPUS_OBSERVED + TESTED + DIFF_VERIFIED`.

The cleaned historical discriminator supports:

- post-Alchemy movement mass;
- combined tower + towed-ship mass;
- proportional distance reduction under insufficient Tow fuel.

Production caveat: knowing the formula does not mean the product knows the Tow-phase fuel value. IntelBoard must continue to fail closed where only a non-phase-aligned snapshot is available.

Finite-fuel Intercept likewise has a supported fuel formula in the lab evidence, but the production client must not treat snapshot neutronium as Intercept-phase fuel. A withheld endpoint in this case is a `phase_state_required` blocker, not evidence that the formula itself is unknown.

True-partial normal-movement fuel semantics are supported by the lab evidence as `CORPUS_OBSERVED + TESTED + DIFF_VERIFIED`. The verified path charges a geometrically partial route for the continuous nominal one-turn leg before Host integer endpoint rasterization; positive insufficient fuel then prorates that one-turn leg and applies Host major/minor-axis projection.

That exact **normal-speed Move Most** path is now deployed in production. It is covered by the historical `360690/T164/ship41` discriminator and no longer emits `unsupported_partial_waypoint` in the supported normal-speed path. The old enum/classifier value remains only for compatibility with older rows.

Zero-fuel normal movement and insufficient-fuel Gravitonic movement remain outside the supported production subset and continue to fail closed. Tow and Intercept remain phase-state-sensitive even where their underlying fuel formulas are supported.

Tow contests/chains/cycles, web-hit interruption details and other special interactions remain separately scoped and must not be smuggled into the base rule.

### Pending movement acceptance

Dedicated browser acceptance is still required for the explicit Tow draft path:

- save target;
- drafted-target precedence;
- `PREDICTED TOW` / `PREDICTED TOWED` rendering;
- clearing/validation when switching missions or combining Tow with Intercept.

## Combat / Battle Planner

The low-level combat simulation and historical replay stack is materially advanced, but this is not yet a complete reconstructed Host combat phase.

Two previously stale production formulas were independently rechecked against immutable downloaded historical games in `planets-lab` and corrected:

### Federation recovery

```text
next_shield = min(100 - damage, shield + 25)
```

Corpus recheck: 48/48 corrected vs 38/48 old formula; 10 corrected-only discriminators and no old-only counterexample.

### Native planet beam tech

```text
ROUND(SQRT(DP / 2))
```

Corpus recheck: 1036/1036 corrected vs 712/1036 old truncation; 324 corrected-only discriminators and no old-only counterexample in the ordinary Classic scope.

Both corrected rules are deployed and have dedicated IntelBoard regression tests.

Remaining Host-combat research is mostly orchestration rather than these formulas: engagement eligibility, opponent/queue selection, side assignment, priority/mission/diplomacy interactions, capture continuation, repair boundaries and planet/base participation order.

## Private refresh / stale-state safety

The production client refreshes running games automatically. A successful transport-level HTTP response is not considered proof that all private observers refreshed successfully.

Current behavior:

- total per-observer refresh failure is surfaced as a user-visible warning with concrete detail;
- stale private snapshots are not fed into current-turn fact tables when their turn differs from canonical game turn;
- an explicit mismatch warning shows canonical and factual turns;
- map display of the stale factual snapshot remains allowed because the map identifies its own factual turn.

The earlier stale-map incident caused by a stale proxy endpoint is considered operationally resolved. Reopen it only on a concrete regression.

## Communications

Communications remain closed absent regression. Accepted runtime/browser behavior includes canonical private grouping, race-first labels, the Robots three-message case and correct Message-vs-Reply handling for the historical unresolved root. Visual grouping never changes factual recipient provenance.

## Threat / inference layer

Existing threat analysis is useful product infrastructure and should be developed in place. It can combine historical mass observations, VCR-revealed weapons, constrained loadout possibilities, likely target/attack-group context, defender/base context, ETA and military-score evidence.

Deterministic post-combat replay state and analyst-confirmed state may enrich analysis, but both remain separate from factual observations and must be labelled accordingly.

## Current next priorities

1. Complete Tow-target browser acceptance and record the observed runtime behavior.
2. Use deployed blocker provenance on real current rows to inventory remaining `implementation_gap`, `phase_state_required` and `unsupported_host_rule` cases before selecting the next mechanics transfer.
3. Preserve phase-state boundaries for finite-fuel Tow and Intercept; supported formulas do not justify substituting snapshot fuel.
4. Extend analyst/threat UX using existing provenance and prediction layers rather than inventing new factual state.
5. Let `planets-lab` continue Host combat ordering research independently; product work should not block on a complete NuHost reconstruction.

## Deliberately not claimed

- Full Host combat ordering is not reconstructed end-to-end.
- Every race-specific ability is not reconstructed.
- Full minefield lifecycle / RNG is not reconstructed.
- Every Tow contest/chain/cycle interaction is not reconstructed.
- A prediction is not factual just because it is deterministic.
- A snapshot field is not assumed to be a phase-state field without evidence.
- Upstream turn submission is not considered complete until an explicit review/write/reconciliation workflow is implemented and accepted.
