# Planets Intel — Current Handoff

Updated: 2026-09-05

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
HEAD:       31fd3db554d5c7f77e19afa83214138fdb764579
BUILD:      OK
TESTS:      OK — 257
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

Later GitHub commits may exist. Do not claim those runtime-validated until a fresh deploy/output is supplied.

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

Battle Planner picker/editor UX and loadout-source fixes are browser-accepted. Do not reopen them without new evidence.

Simulator default precedence:

```text
current factual/private/shared state
  > analyst-confirmed post-VCR state
  > deterministic replay post-VCR state
  > same-turn factual combat-start fallback
  > simulation assumption
```

For a VCR from the immediately preceding Host turn, only post-combat mutable state may cross the Host boundary; combat-start ammunition does not.

Material combat validation checkpoint:

- deterministic VCR replay: earlier `145/145` supported, `0` payload conflicts, `2/2` analyst checks; corpus later grew to 148 VCRs;
- ship sequence carry: 42 same-turn/same-location transitions matched comparable terminal -> next factual start state;
- strong ship-sequence anchor: game `680933`, T42, Virgo `#10`, VCR `201 -> 202`, `shield=0 damage=12 crew=1724 fighters=39`;
- planet/starbase carry: only Launa Planet `#75`, game `682909`, T9, VCR `9 -> 10`, starbase present, shield `0 -> 0`; no repeated no-starbase planet chain;
- Lizard 150% endurance: 37 comparable, 15 sensitive, 15 terminal-state-only changes, 0 winner changes; keyed runtime regression `2/2` matched;
- Federation +3 carrier bays: Kittyhawk game `683230`, T15, VCR 20, hull 6 bays -> factual VCR 9 bays; keyed runtime regression `1/1` matched;
- Federation damaged-start weapon continuity and between-fight 25% shield recovery remain unvalidated because no isolating factual cases exist;
- right-side carrier +360 balance remains unvalidated: 12 candidate shapes, only 1 ammo-isolating shape, 0 usable next-turn same-position mass observations. Never substitute `VCR mass - hull mass` for evidence.

One old screenshot showed `Battle sequence odds failed: 502 Proxy Error` with the UI set to 10,000 battles. It has not been reproduced or tied causally to 10,000 trials. Investigation remains deferred.

## Game chooser checkpoint

The chooser is game-centric rather than account-centric:

- one card per game;
- observer selection through compact `Open as ...` controls;
- local linked accounts plus active/approved Intel Share peers are labelled under their turn-status slot with `↑ nickname`;
- inactive/dead slots are visibly struck through, including an associated local/peer label.

Browser runtime accepted the deduplicated chooser. The dead-slot strike commit was subsequently deployed successfully as part of the 253-test checkpoint. Do not reopen this UI without new evidence.

## Movement fuel — implementation complete for the verified subset

Fuel mechanics were transferred from the already researched `Numillyash/planets-lab` rule layer, not reconstructed from memory.

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

Movement mass is reconstructed from factual components:

```text
hull mass (engine mass already included)
+ fitted beam component mass
+ fitted torpedo-tube component mass
+ torpedoes
+ fighters
+ neutronium
+ supplies
+ clans
+ duranium
+ tritanium
+ molybdenum
```

Do not use raw Planets.nu `ship.mass` as Host movement mass. Do not substitute hull weapon capacity for factual installed weapon count. Ambiguous generic `ammo` stays unresolved.

Verified positive insufficient-fuel rule:

```text
actual distance = waypoint distance * fuel available / fuel required
```

The continuous distance is converted to coordinates with the Host major/minor-axis integer projection.

Production modules:

```text
backend/app/services/movement_fuel.py
backend/app/services/movement_fuel_policy.py
backend/app/services/movement_prediction_runtime.py
backend/app/scripts/movement_fuel_runtime_diagnostic.py
```

Waypoint runtime order is currently:

```text
ordinary geometry
-> factual movement-mass reconstruction
-> documented fuel calculation
-> verified fuel proration when applicable
-> warp-well resolution
-> later Intercept sees the fuel-adjusted waypoint position
```

If finite-fuel endpoint cannot be resolved safely, the predicted waypoint position becomes unresolved instead of leaking geometric output as factual-looking certainty.

### Fuel evidence closure

`Numillyash/planets-lab` historical 12-game corpus already established the strict fuel-proration subset as:

```text
DOCUMENTED + CORPUS_OBSERVED + TESTED + DIFF_VERIFIED
fuel_proration_explained = 6
Nu exact Host matches = 6
Nu-only discriminating matches = 3
VGAP3-style control matches = 0
targeted v6 regression set = 16 passed
```

`planets-intel` mirrors the verified 200-KT / 60-ly / 12-KT-required / 11-KT-available -> 55-ly reference vector in its own regression tests.

The production DB cannot provide additional finite-fuel runtime evidence. Read-only diagnostic on the last confirmed server deploy reported:

```text
latest_factual_groups:                 26
factual_unlimited_groups:              26
factual_fuel_enabled_groups:            0
factual_owner_ships:                  356
factual_waypoint_items:               180
factual_unlimited_waypoint_items:     180
factual_fuel_enabled_waypoint_items:    0
factual_fuel_status_counts: unlimited=180
```

Therefore do not keep asking for finite-fuel runtime validation from the current `planets-intel` DB. The finite-fuel checkpoint is closed by the differential-verified `planets-lab` evidence plus the cross-repository production regression.

Remain fail-closed for separate mechanics not covered by the strict fuel subset:

- zero-fuel movement;
- insufficient-fuel Gravitonic movement;
- insufficient fuel on an already partial waypoint;
- pre-movement transfers / Crystal web drain / other fuel-state mutation;
- Tow movement mass/order until Tow is integrated;
- finite-fuel Intercept until Tow and Intercept ordering are integrated.

## Current development focus — Tow before Move Most / Intercept

Roadmap now resumes:

```text
Tow resolution
-> integrate Tow ahead of Move Most / Intercept
-> resolve finite-fuel Intercept on the unified movement state
-> unified movement prediction / turn review
```

### Tow evidence transferred from planets-lab

`planets-lab` route-equivalent visible Tow is `TESTED + DIFF_VERIFIED` on the historical corpus.

Verified evidence semantics:

- owner-visible Tow mission;
- Tow mission ID `6`;
- target ID exposed as `mission1target` / `mission1_target_id`;
- tower and target colocated before movement;
- tower and target end at the same non-stationary destination;
- if several visible towers are route-equivalent, route evidence is valid but winning tower identity remains ambiguous and must not be invented.

Host movement phase ordering is:

```text
Tow -> Move Most -> Intercept
```

The research simulator also contains the narrow Tow lock mechanics (engine eligibility, tower fuel where finite, colocation, four-fingers target break) and Tow movement using combined tower + target movement mass.

### New strict production Tow primitives

Current development adds:

```text
backend/app/services/movement_tow.py
backend/app/scripts/movement_tow_runtime_diagnostic.py
backend/tests/test_movement_tow.py
```

The first production-facing Tow lock subset is deliberately stricter than the lab simulator:

- unique factual tower -> target only;
- invalid/missing target fails;
- tower with fewer than two engines fails;
- finite-fuel tower without fuel fails;
- non-colocated target fails;
- four-fingers target-break predicate is evaluated only when all required factual inputs exist;
- unknown target fuel/engine/waypoint remains unknown;
- same-target Tow contests fail closed rather than selecting a winner by ship ID;
- Tow chains/cycles fail closed rather than inventing resolution order.

This pure lock layer does not yet mutate movement prediction. The read-only diagnostic must be run first to measure the actual current factual Tow population and missing prerequisites.

### Draft-model boundary

Current local ship order draft schema still models movement modes only as:

```text
waypoint
intercept
```

There is no `tow_target_ship_id` field yet. Do not abuse `intercept_target_ship_id` for Tow. Initial Tow runtime work may inspect factual upstream Tow orders only. If local Tow planning is added later, introduce a deliberate draft/API/frontend field and migration.

## Immediate next action

Deploy the latest branch after Tow CI is green (or use the production deploy, which runs build/tests itself), then run:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== TOW RUNTIME AUDIT ====="
docker compose exec -T backend \
  python -m app.scripts.movement_tow_runtime_diagnostic
```

Paste the complete deploy result and Tow diagnostic JSON.

Interpretation goals:

- count actual owner-private Tow mission records;
- verify target IDs and target visibility;
- measure unique strict lock candidates;
- expose missing factual prerequisites without turning them into zero;
- identify same-target contests and Tow chains/cycles;
- only after this audit, wire the supported unique Tow subset ahead of Move Most/Intercept.

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
