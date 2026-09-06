# Planets Intel — Current Handoff

Updated: 2026-09-07

GitHub is the source of truth. Active development remains on `feature/operational-ui`. A fresh chat must read this file together with `NEW_CHAT_START.md`, `PROJECT_STATE.md` and `BATTLE_PLANNER_HANDOFF_2026-08-25.md`, then inspect the actual branch HEAD and `/opt/planets-intel` before deploying.

## Repository / runtime

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production backend image embeds the React/Vite frontend.
- Never infer server HEAD from chat history; inspect it before every deploy.

Last explicitly runtime-confirmed deploy with full output:

```text
HEAD:       de16e15d4104afa402215bd54c12260b93d4d379
BUILD:      OK
TESTS:      OK — 286
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

The same HEAD passed GitHub CI including backend tests, frontend type-check/build and production image build.

## Hard invariants

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Deterministic replay is derived evidence, never a factual observation. Local order drafts and predictions are planning state, never canonical Planets.nu facts.

## Battle Planner / combat checkpoint

Battle Planner picker/editor UX and combat regression work are materially closed on the available corpus. Do not reopen without new evidence.

Key unresolved combat evidence gaps remain explicit:

- Federation damaged-start weapon continuity;
- Federation 25% between-fight shield recovery;
- no-starbase multi-wave planet carry;
- hidden starbase persistent state after hull damage;
- right-side carrier +360 probabilistic balance rule.

One old screenshot showed `Battle sequence odds failed: 502 Proxy Error` with 10,000 battles selected. It has not been reproduced or causally tied to trial count and remains deferred.

## Game chooser checkpoint

The chooser is game-centric rather than account-centric and browser-accepted:

- one card per game;
- observer selection through compact controls;
- combined slot status with local/shared observer labels;
- inactive/dead slots visibly struck through.

New games are also discovered by the background private-refresh loop rather than waiting for canonical scheduler membership. Runtime logs confirmed live discovery and private refresh for a newly appearing game. Do not reopen chooser/refresh without new evidence.

## Movement fuel — closed verified subset

Fuel mechanics were transferred from `Numillyash/planets-lab`, not reconstructed from memory.

Documented normal movement formula:

```text
Fuel Use = TRUNC(
    Fuel Factor
    * TRUNC(Total Mass / 10)
    * TRUNC(Distance Traveled)
    / Max Distance Per Turn
    / 10000
)
```

`Max Distance Per Turn` is `warp²`, doubled for Gravitonic movement.

Movement mass is reconstructed from factual physical components. Do not use raw Planets.nu `ship.mass` as Host movement mass and do not substitute hull weapon capacity for fitted equipment.

Positive insufficient-fuel normal movement uses the Nu proportional-distance rule and Host integer major/minor-axis projection. The historical 12-game `planets-lab` corpus differential remains the finite-fuel evidence source:

```text
fuel_proration_explained = 6
Nu exact Host matches = 6
Nu-only discriminating matches = 3
VGAP3-style control matches = 0
```

The production DB currently contains only unlimited-fuel factual groups, so no additional finite-fuel runtime sample exists there. Do not keep requesting one from current games.

## Tow — production checkpoint closed for the strict unlimited-fuel subset

Host movement phase order used by prediction is:

```text
Tow -> Move Most -> Intercept
```

Historical route-equivalent visible Tow remains `TESTED + DIFF_VERIFIED` in `planets-lab`.

Production Tow modules:

```text
backend/app/services/movement_tow.py
backend/app/services/movement_prediction_runtime.py
backend/app/scripts/movement_tow_runtime_diagnostic.py
backend/tests/test_movement_tow.py
backend/tests/test_movement_prediction_tow_runtime.py
```

The production strict resolver preserves these boundaries:

- Tow mission ID `6` / `mission1target` from factual private state;
- valid visible target;
- tower requires at least two engines;
- exact colocation required;
- Four Fingers is evaluated only from known non-fuel inputs;
- same-target contests remain ambiguous;
- Tow chains/cycles fail closed only inside the affected connected component;
- finite-fuel Tow remains unresolved because Tow-phase fuel and combined tower+target physical mass are not yet reconstructed at that Host boundary;
- Tow + planetary warp-well interaction remains fail-closed;
- no arbitrary winner is inferred from ship ID ordering.

The movement runtime now resolves the supported Tow subset before ordinary Move Most / Intercept, reserves known post-Tow positions for later Intercept, suppresses false ordinary movement for unresolved Tow participants, and exposes Tow metadata in movement-prediction responses. Map vectors distinguish `PREDICTED TOW` / `PREDICTED TOWED`.

### Runtime Tow audit — 2026-09-07

Read-only production diagnostic on deployed HEAD `de16e15d...` reported:

```text
latest_factual_groups:       29
catalog_missing_groups:       0
unlimited_fuel_groups:       29
fuel_enabled_groups:          0
owner_ships:                385
groups_with_tow:             13
factual_tow_missions:        25
tow_missions_missing_target:  0
tow_targets_visible:         25
tow_targets_not_visible:      0
same_target_contest_groups:    0
tow_chain_groups:              0
tow_attempts_evaluated:       25
strict_locked_candidates:     25
uncertain_attempts:            0
status_counts: locked=25
```

This closes the current factual unlimited-fuel Tow lock checkpoint: every currently observed Tow attempt is inside the strict supported subset. It does **not** validate finite-fuel Tow and does not weaken the fail-closed boundaries above.

## Draft-model boundary / next Tow product gap

Current ship draft schema still has only:

```text
movement_mode = waypoint | intercept
intercept_target_ship_id
```

There is no `tow_target_ship_id` field. A local draft that newly selects `Try to Tow` therefore must not reuse a stale factual `mission1target`; runtime deliberately marks it unresolved and withholds ordinary movement.

The next draft-side Tow change, when implemented, must add a deliberate `tow_target_ship_id` contract through migration + model + schema + service + API + frontend picker. Do not abuse `intercept_target_ship_id` for Tow.

## Immediate development order

```text
1. Add explicit local Tow-target draft contract and UI selection.
2. Feed drafted Tow targets into the already integrated Tow-before-Move-Most runtime.
3. Resolve finite-fuel Intercept semantics on the unified movement state using researched evidence; keep unsupported fuel/Tow ordering fail-closed.
4. Consolidate Tow / Move Most / Intercept into a unified movement prediction / turn-review model.
5. Continue broader draftable missions/cargo/planet/starbase orders and explicit reviewed upstream write-back.
```

## Communications status

True Planets.nu threaded replies remain validated and working through:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Do not reopen Communications without new evidence. See `docs/architecture/COMMUNICATIONS_REPLY_CONTRACT.md`.

## Server preflight

```bash
cd /opt/planets-intel

git fetch origin
printf 'BRANCH: '; git symbolic-ref --quiet --short HEAD || true
printf 'HEAD:   '; git log -1 --oneline
printf 'DIVERGENCE HEAD...origin: '; git rev-list --left-right --count HEAD...origin/feature/operational-ui
git status --short

docker compose ps
curl -fsS http://127.0.0.1:18080/api/health && echo
```

If clean and behind:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

Do not claim runtime validation from static code or CI alone. Runtime claims require actual server/browser/diagnostic output.
