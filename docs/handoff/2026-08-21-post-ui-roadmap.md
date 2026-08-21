# Post-operational-UI roadmap — 2026-08-21

This checkpoint reflects the actual `feature/operational-ui` state after the August 19–21 runtime/UI pass. `PROJECT_STATE.md` and `CURRENT_HANDOFF.md` contain durable architecture, but their priority lists predate a substantial amount of completed Battle Planner, VCR, timing and routing work.

## Current milestone state

Implemented and substantially runtime-tested during the current pass:

- shared `/intelboard` observer/game home with two-column operational chooser;
- canonical turn-state reconciliation, unknown/dead/computer semantics and missed-turn warnings;
- background private-intel refresh with observer-set dedup;
- deterministic VCR replay with individual fighter tracks, fighter/dogfight effects, beam/torpedo presentation and factual combat counters;
- VCR-driven Battle Planner with repeated deterministic battle sampling and terminal-stat summaries;
- player activity timing with local/UTC presentation and cross-game aggregation by canonical username;
- map VCR review state and host-report notification clustering;
- SPA surface/tab route state via History API (`view` / `tab` query params);
- unified Games / Dashboard / Intel / Starmap / Turn navigation;
- global account management moved from per-game Dashboard to the shared `/intelboard` home.

Hard invariants remain unchanged:

```text
known zero != unknown
fact != inference != simulation
combat-time fact != current fact
missing data != zero
unknown Host behavior = fail-closed
```

## Immediate validation gate

Before starting a new large feature:

1. Build production image from current `feature/operational-ui` HEAD.
2. Run full backend suite and frontend production build.
3. Deploy and verify `/api/health`.
4. Runtime-check:
   - `/intelboard` contains collapsible Account settings and no observer-specific home URL;
   - per-game Dashboard no longer has an Accounts button;
   - nav alignment is identical between Starmap / Dashboard / Intel;
   - Dashboard/Intel tabs survive reload and Back/Forward without page reload;
   - T20 host-report clusters and reviewed VCR map notifications behave correctly.
5. Update the durable `CURRENT_HANDOFF.md` once this gate passes.

## Roadmap after the validation gate

### 1. Operational intelligence completion

Goal: make current-turn intelligence explain changes rather than only display observations.

High-value items:

- Priority Point attribution / production-queue evidence:
  - separate factual PP delta from possible causes;
  - recognize supported combat PP, recycle evidence and unused build-allocation possibilities;
  - never assert a cause unless evidence is sufficient.
- Finish Fight-or-Fail risk semantics from factual Host/game rules instead of generic missed-turn thresholds.
- Continue accumulating `first open` polling observations and validate whether cross-game activity profiles remain useful at larger sample sizes.
- Improve notification/review workflow for host reports, combat and communications without deleting factual history.

### 2. Unified movement-phase model

This is the largest missing deterministic planning subsystem in the durable architecture.

Implement in this order:

1. fuel consumption / reachability model;
2. Tow resolution;
3. integrate Tow ahead of normal movement / Move Most / Intercept;
4. consolidate normal movement, warp wells, Tow, Intercept and unresolved envelopes into one reproducible `ShipPrediction` / movement-phase result;
5. expose uncertainty explicitly when Host behavior or required facts are unavailable.

The result should feed both starmap prediction and turn review rather than maintain separate movement implementations.

### 3. Battle Planner -> operational planning integration

The standalone simulator exists; next step is to connect it to real planning workflow.

- launch scenarios directly from selected map ships/planets/VCR evidence;
- preserve `current factual`, `combat-time factual`, `manual assumption` and `simulation` provenance independently;
- support sequential likely combats / battle-order review;
- make result summaries usable from the map without treating simulated outcomes as intel facts.

### 4. Order drafting expansion

Current local drafts are scaffolding. Expand explicit draftable orders while keeping all writes local:

- missions and mission parameters;
- waypoint / warp / intercept / tow target;
- cargo transfers where facts and API semantics are understood;
- planet and starbase orders;
- build orders;
- validation against known game rules and available resources.

No draft changes canonical observations.

### 5. Turn review

Build a single pre-submit review surface combining:

- changed orders;
- predicted movement with uncertainty;
- fuel/resource validation;
- likely combats / Battle Planner links;
- unresolved warnings;
- stale-observation/provenance warnings.

This is the safety boundary before any upstream write path.

### 6. Explicit Planets.nu write path

Only after draft and review semantics are stable:

1. implement a narrow Planets.nu write adapter;
2. save explicit reviewed orders upstream;
3. keep submit-turn as a separate explicit action;
4. reconcile saved/submitted state back against upstream facts;
5. post-host reconciliation must distinguish accepted orders, changed facts and predictions that did not occur.

## Recommended next feature after current deploy

Start with **movement fuel model**, unless runtime testing reveals an operational-UI correctness defect that should block the milestone.

Why fuel first:

- movement prediction already exists and is useful;
- without fuel, reachability can still present physically impossible plans;
- Tow depends on movement/fuel semantics and should follow immediately;
- both are prerequisites for trustworthy turn review and eventual upstream submission.

Priority Point attribution can be developed in parallel as an intelligence-only feature because it does not block the write-path architecture.
