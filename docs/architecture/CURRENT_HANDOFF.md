# Planets Intel — Current Handoff

Updated: 2026-08-26

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
HEAD:       1f9516f33fd4f898a7ee685de125b89e8350e299
BUILD:      OK
TESTS:      OK — 231
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

Later GitHub commits implement movement fuel. Do not claim those runtime-validated until a fresh deploy/output is supplied.

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

Important current intel precedence for simulator defaults:

```text
current factual/private/shared state
  > analyst-confirmed post-VCR state
  > deterministic replay post-VCR state
  > same-turn factual combat-start fallback
  > simulation assumption
```

For a VCR from the immediately preceding Host turn, only post-combat mutable state may cross the Host boundary; combat-start ammunition does not.

### Deterministic VCR replay

Earlier full audit: `145/145` unique VCRs supported, `0` payload conflicts, `2/2` analyst-confirmed state checks matched. Corpus later grew to `148` unique VCRs.

### Ship sequence carry

`combat_chain_regression.py` found 42 same-turn/same-location ship transitions. Comparable `damage`, `crew`, `torpedoes`, `fighters`, and non-Federation shield all matched deterministic terminal -> next factual VCR start.

Strong anchor: game `680933`, turn `42`, Virgo `#10`, VCR `201 -> 202`:

```text
shield=0 damage=12 crew=1724 fighters=39
```

The VCR 201 deterministic terminal state exactly becomes VCR 202 factual start state.

### Planet/starbase sequence carry

Only one repeated planetary defender exists: game `682909`, turn `9`, Launa Planet `#75`, VCR `9 -> 10`, starbase present. Shield carry `0 -> 0` matches. No repeated no-starbase planet chain exists; hidden persistent starbase state remains fail-closed.

### Lizard 150% endurance — closed/anchored

Runtime sensitivity audit over 37 factual Lizard VCRs:

```text
comparable:               37
sensitive:                15
insensitive:              22
outcome_changed:           0
terminal_only_changed:    15
ship_vs_ship_sensitive:   14
ship_vs_planet_sensitive:  1
```

Keyed runtime regression:

```text
backend/app/scripts/combat_lizard_regression.py
baselines: 2
matched:   2
failed:    0
```

VCR 201 is additionally anchored by the next factual VCR; VCR 216 protects a sensitive case with the Lizard ship on RIGHT.

### Federation — direct evidence anchored, gaps explicit

Direct factual carrier evidence:

```text
game 683230 · T15 · VCR 20
KITTYHAWK CLASS CARRIER
hull bays = 6
VCR bays  = 9
delta     = +3
```

Keyed runtime regression `combat_federation_regression.py`: `1/1` matched.

Current corpus has:

```text
damaged Federation combat starts:                 0
same-turn same-location Federation transitions:   0
```

Therefore damaged-start full-weapon continuity and 25% between-fight shield recovery remain explicitly unvalidated by real corpus evidence.

### Right-side carrier balance — unvalidated, stop here

Strict factual audit `combat_right_balance_evidence.py` at the current runtime checkpoint:

```text
unique_vcrs:                          148
candidate_shapes:                      12
ammo_mass_isolating_shapes:             1
next_turn_same_position_mass_observed:  0
owner_observed_exact_cases:             0
foreign_observed_supporting_cases:       0
```

No +360 conclusion is justified from the current corpus. Do not fall back to `VCR mass - hull mass`; load/ammunition confound that comparison. Reopen only if new factual mass evidence creates an isolating case.

### Deferred one-off 502

One old screenshot showed `Battle sequence odds failed: 502 Proxy Error` while the UI contained `10000` battles. It has not been reproduced or tied causally to 10,000 trials. Investigation remains deferred.

## Current development focus — movement fuel

Combat validation is materially closed as far as the current corpus permits. Roadmap now resumes:

```text
movement fuel
-> Tow resolution before Move Most/Intercept
-> unified movement prediction / turn review
```

### Evidence source

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

Do not use raw Planets.nu `ship.mass` as movement mass. Do not substitute hull weapon capacity for factual installed weapon count. Ambiguous generic `ammo` stays unresolved.

### Verified insufficient-fuel subset

`planets-lab` has documented + corpus-observed + tested + differential-verified positive-fuel proration cases:

```text
actual distance = waypoint distance * fuel available / fuel required
```

The resulting continuous distance uses Host major/minor-axis integer projection.

Production intentionally applies proration only to the verified subset:

- positive fuel;
- normal-speed ship;
- waypoint reachable within the ordinary one-turn movement allowance.

Remain fail-closed for now:

- zero-fuel movement;
- insufficient-fuel Gravitonic movement;
- insufficient fuel when the waypoint is already farther than the one-turn range;
- pre-movement Crystal web drain / transfers / other fuel-state mutation;
- Tow mass and Tow ordering;
- finite-fuel Intercept until Tow is resolved first.

### New production modules

```text
backend/app/services/movement_fuel.py
backend/app/services/movement_fuel_policy.py
backend/app/services/movement_prediction_runtime.py
backend/app/scripts/movement_fuel_runtime_diagnostic.py
```

The API route now uses `movement_prediction_runtime.py`. It is a runtime facade over the existing movement pipeline, using request-local context rather than creating a second movement engine.

For waypoint Move Most:

```text
ordinary geometry
-> factual movement-mass reconstruction
-> documented fuel calculation
-> verified fuel proration when applicable
-> warp-well resolution
-> later Intercept sees the fuel-adjusted waypoint position
```

If finite-fuel endpoint cannot be resolved safely, waypoint position becomes unresolved instead of leaking the old geometry as a factual-looking answer.

Finite-fuel Intercept remains visible as a geometry preview but is marked `certain=false` with `fuel_status=unresolved_intercept` until Tow/fuel ordering is implemented.

Movement response items now expose:

```text
fuel_status
movement_mass
fuel_available
fuel_factor
fuel_required
fuel_used
fuel_limited
fuel_basis
fuel_reason
```

### Fuel commits in current development pass

```text
bc7daaf026f61d7e5531a80f44e2a86f7bb6e9ba  feat: add verified movement fuel primitives
5350a4d3b9b84a0bb14e4c0464bcc6f5ce2abe13  test: cover verified movement fuel primitives
e33b2e06fea1e5e47bdcf539a728435d495de203  feat: resolve waypoint fuel policy
7ec2963f6b068a44f22335f0f9b71b68b2d2173d  test: cover waypoint fuel policy boundaries
acbf370e89f5bf44faf570716aacf06c7ea3c3b2  feat: apply fuel to movement prediction runtime
366876252f12a74d5d9aff79fef7e26f30f45b77  refactor: route movement prediction through fuel runtime
49645d8d5cf65ebcc276f62b2d2701f6ea1eea40  feat: expose movement fuel evidence fields
1e497f9cdd2945b369bea8ec6cbf403a62f50f94  feat: type movement fuel evidence
3f643b3edf0ff2fe235918dd6b4f0e4784810b37  feat: add movement fuel runtime diagnostic
e97e8a4357a38c929d01ffc626f3a89ed4424370  test: cover fuel-aware movement runtime facade
```

## Immediate next action

Deploy latest `feature/operational-ui` and run the read-only real-data diagnostic:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== MOVEMENT FUEL RUNTIME ====="
docker compose exec -T backend \
  python -m app.scripts.movement_fuel_runtime_diagnostic
```

Paste the full deploy result and diagnostic JSON.

Interpretation goals:

- verify how many current saved waypoint drafts have fully reconstructible factual movement mass;
- inspect real `fuel_required / fuel_available` values;
- confirm any `limited` waypoint cases use the fuel-adjusted endpoint;
- classify `unknown` and fail-closed cases without filling gaps with zero;
- after runtime validation, start Tow resolution ahead of Move Most/Intercept.

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
