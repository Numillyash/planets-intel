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
- Expand cross-game player intelligence by canonical username where provenance and access scope are valid.
- Improve combat/intel summaries so VCR, reports, score deltas and factual ship observations explain one another without collapsing fact/inference/simulation layers.

### 2. Diplomacy and communications write-path

This is now the preferred first upstream-write feature. It is intentionally narrower than ship/order submission.

Current state:

- Diplomacy is read-only and exposes factual/raw relation data.
- Communications are available as read-side intelligence, but there is no IntelBoard compose/send workflow.

Implement in this order:

1. Reverse/validate the Planets.nu endpoints and payload semantics for sending messages and changing diplomacy.
2. Add a narrow authenticated backend adapter bound to one explicit linked observer/account.
3. Add message composition in the Communications UI:
   - explicit recipient(s);
   - body preview;
   - explicit Send action;
   - refresh/reconcile after successful send;
   - never silently retry a write.
4. Add editable outgoing diplomacy in the Diplomacy UI:
   - show current factual `you -> them` and `them -> you` separately;
   - present only named relation states whose numeric mapping is validated;
   - changing `you -> them` requires an explicit action/confirmation;
   - refresh/reconcile from upstream after the write.
5. Keep messages/diplomacy separate from Submit Turn and from local ship-order drafts.

Writes must always be explicit, observer-scoped and auditable. A failed/unknown upstream response must not be presented as a successful change.

### 3. Battle Planner -> intelligence integration

The standalone simulator exists. The near-term goal is intelligence support, not order automation.

- launch scenarios directly from selected observed ships/planets/VCR evidence;
- preserve `current factual`, `combat-time factual`, `manual assumption` and `simulation` provenance independently;
- compare observed enemy fleets against known/reconstructed friendly forces;
- support sequential combat analysis where useful for threat assessment;
- make result summaries usable from the map/intel surfaces without treating simulated outcomes as facts.

### 4. Player / opponent dossiers

Build cross-game intelligence around canonical player identity where the user has access to the source games.

Candidate evidence:

- Ready/Open activity profile across current games;
- race/game participation;
- historical score trends;
- recurring ship/fleet patterns;
- diplomacy history where factual data exists;
- communications history available to the observer;
- combat/VCR behavior and known carrier/loadout evidence.

This should be descriptive intelligence first. Do not turn sparse history into personality claims or unsupported deterministic predictions.

### 5. Notification and review center

Unify actionable intelligence notifications:

- unread/new communications;
- VCRs;
- explosion/host reports;
- notable score/military/PP changes;
- Fight-or-Fail risk;
- newly observed or materially changed enemy ships/fleets.

Review state remains local UI state unless the upstream API itself has a factual read/unread state that is explicitly modeled.

### Deferred: movement, fuel, Tow and turn-order workflow

Fuel modeling, Tow resolution, unified movement phases, expanded local order drafting, turn review and full Planets.nu order/submit-turn write paths are deliberately deferred.

Reason: the currently active games on the linked accounts do not use fuel, and the product priority is intelligence/analysis rather than reproducing the complete turn-order client.

Existing movement prediction remains available, but new work should not prioritize fuel/Tow until an active-game requirement or a higher-level product need makes it relevant.

## Recommended next feature after current deploy

Start with the **Diplomacy + Communications narrow write-path**, while continuing intelligence-only work in parallel.

Recommended sequence:

1. validate and deploy the current Home/Accounts/nav checkpoint;
2. reverse/confirm Planets.nu message and diplomacy write endpoints using the linked-account API model;
3. implement message sending with explicit confirmation/reconciliation;
4. implement editable outgoing diplomacy with validated relation-state mappings;
5. return to Priority Point attribution, Fight-or-Fail semantics and opponent/cross-game intelligence;
6. leave fuel/Tow/order submission deferred until they become relevant to active games.
