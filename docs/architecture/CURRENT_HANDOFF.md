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

Last explicitly runtime-confirmed deploy with full deploy output:

```text
HEAD:       db1fec23715f4bda111d619daaa678cce9048cad
BUILD:      OK
TESTS:      OK — 214
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

Later GitHub commits exist. The compact corpus summary was also run successfully from the production backend after it was added, but the user did not include a fresh deploy/HEAD block with that specific run, so do not invent the exact server HEAD for it.

## Hard invariants

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Battle Planner loadout edits are simulation assumptions only. Deterministic replay is derived evidence, never a factual observation.

## Battle Planner UX checkpoint — closed

The 2026-08-25 picker/editor/UI work is browser-validated and should not be reopened as pending work.

Confirmed in deployed UI:

- separate `Known ships`, `Known planets`, `Generic ship / planet` sources;
- known ships grouped by race;
- support ships hidden by default and restored by `Show support ships`;
- zero-installed / positive-capacity hulls, including `VIRGO CLASS BATTLESTAR #19`, expose simulation weapon controls up to hull capacity;
- generic ships use factual race-catalog hull membership;
- generic planets/starbases work on RIGHT;
- multiple LEFT/RIGHT combatants, queue reorder and side swap work;
- deterministic and normal odds paths work;
- VCR validation-lab spacing and compact starbase layout were accepted;
- legacy combined-picker state/helper code was removed.

## Deferred observation — sequence odds 502

One browser screenshot showed:

```text
Battle sequence odds failed: 502 Proxy Error
```

The UI happened to contain `10000` battles, but this is one observation only. It is not established that 10,000 battles caused it or that there is a reproducible threshold bug. Queue logic was later confirmed with the classic 118-seed series and a single deterministic run.

This investigation is explicitly deferred. If reopened later: reproduce deliberately, measure backend/proxy timings and logs, and do not blindly raise timeouts.

## Real VCR deterministic replay — validated

Read-only diagnostic:

```text
backend/app/scripts/combat_regression_dump.py
```

Validated corpus result:

```text
unique_vcrs:               145
payload_conflicts:           0
catalog_missing:             0
replay_supported:          145
replay_unsupported:          0
analyst_checks:              2
analyst_matches:             2
analyst_mismatches:          0
analyst_not_comparable:      0
```

All observed game catalogs use Classic combat RNG (`combatrng = 0`). `145/145 supported` proves current stored inputs are accepted by the deterministic engine; it does not prove every Host special mechanic has independent factual confirmation.

## Real multi-VCR ship carryover — validated

Read-only diagnostic:

```text
backend/app/scripts/combat_chain_regression.py
```

Runtime found:

```text
ship_appearances:                     206
candidate_same_turn_ship_chains:       23
same_location_transitions:             42
reappearance_after_defeat:              0
federation_race_transitions:            0
non_federation_shield_rule_matches:    42
non_federation_shield_rule_mismatches:  0
```

All 42 same-location transitions matched deterministic terminal -> factual next-VCR start for comparable `damage`, `crew`, `torpedoes`, `fighters`, and non-Federation shield.

Useful real example: game `680933`, turn `42`, Virgo `#10`, VCR `201 -> 202`: terminal `damage=12`, `crew=1724`, `fighters=39`, `shield=0` exactly becomes the next factual combat start even though the ship changes combat side.

The first report printed `matches: 0` due a diagnostic-only aggregation typo (`match` vs public key `matches`). Comparison records were correct. Fixed in:

```text
c79795cf103fcc265a4397db0928c3fb3244816f  fix: count combat chain regression statuses
0f36cf4883c2b25919770525eb25012d3052b926  test: lock combat chain summary counters
```

Federation shield recovery between fights remains unvalidated by real repeated Federation VCRs because `federation_race_transitions = 0`.

## Real planet / starbase multi-wave carryover — checked

Read-only diagnostic:

```text
backend/app/scripts/combat_planet_chain_regression.py
```

Runtime result:

```text
planet_appearances:                    84
candidate_same_turn_planet_chains:      1
same_location_transitions:              1
matches:                                1
mismatches:                             0
shield_matches:                         1
shield_mismatches:                      0
no_starbase_exact_matches:              0
starbase_or_unknown_transitions:         1
```

Only repeated factual planetary defender:

```text
game 682909
turn 9
planet #75 — Launa Planet
VCR 9 -> VCR 10
has_starbase = true
terminal shield 0 -> next factual start shield 0
```

Interpretation:

- shield carry is confirmed for this one starbase transition;
- no repeated no-starbase planet chain exists in the current corpus, so exact DP/fighter/beams/bays/mass carry lacks real chain validation;
- starbase persistent post-damage defense/fighters/tech/damage remains fail-closed because VCR does not uniquely expose it.

Do not weaken that boundary.

## Compact factual combat coverage — runtime checked

Detailed audit:

```text
backend/app/scripts/combat_corpus_coverage.py
```

Compact projection:

```text
backend/app/scripts/combat_corpus_summary.py
```

The compact projection reuses the same classifier; it adds no second combat-classification logic.

Latest runtime counts:

```text
stored_observations:             365
unique_vcrs:                     145
games:                             6
race_ids_with_ship_combat:         9
unique_game_hulls_in_combat:      66

ship_vs_planet:                   84
ship_vs_ship:                     61
starbase_battle:                   7
carrier_battle:                   77
carrier_vs_carrier:                4
carrier_and_torpedo_ship:         18
torpedo_ship_battle:              78
damaged_start:                    22
sub_full_shield_start:            89
unarmed_ship_present:             20
federation_ship_battle:            9
lizard_ship_battle:               37
federation_ship_vs_planet:         4
lizard_ship_vs_planet:             7
right_balance_candidate_shape:     9
```

Race ship-side appearances:

```text
1:  9   (carrier 1)
2: 37   (carrier 0)
3: 24
4: 21
6: 14   (carrier 1)
8: 15   (carrier 10)
9: 19   (carrier 16)
10: 28  (carrier 24)
11: 39  (carrier 29)
```

These are factual input coverage counts only. They do not prove a special rule fired.

## Current development focus — Lizard rule sensitivity

The next autonomous target is Lizard 150% in-combat endurance because the corpus contains 37 factual Lizard ship battles and this branch can be tested without inventing hidden cargo/mass state.

Production Battle Simulator uses the authoritative builder in:

```text
backend/app/services/battle_simulator_runtime.py
```

It deliberately preserves race-2 identity in ship and planet combat. The exact classic engine uses race 2 for the 150% in-combat damage limit; planet-result handling still applies the Nu tidal-force post-combat destruction semantics.

New read-only differential diagnostic:

```text
backend/app/scripts/combat_lizard_rule_sensitivity.py
```

Commits:

```text
53dbfa56e1db8d72c56a4eec8d02a28b75091921  feat: add Lizard combat rule sensitivity diagnostic
492bb2d1478f8796c2bdf7e2caf20fcffe8dda40  test: cover Lizard rule sensitivity helpers
```

Diagnostic semantics:

- select factual VCRs containing race-2 ships;
- replay each factual payload unchanged;
- replay a counterfactual copy with only Lizard ship `raceid` neutralized to `0`;
- same factual seed, weapons, mass, damage, ammo, opponents and persisted rule catalog;
- report whether result labels and/or terminal state change;
- a `sensitive` case means the Lizard endurance branch materially affects deterministic output for that factual combat input;
- this is branch-exercise evidence, not an independent factual proof of Host correctness;
- no observations are modified.

Right-side carrier balance is intentionally not the first differential target: simple `VCR mass - hull mass` would be confounded by changing ship load/ammunition, so do not claim +360 factual validation from hull mass alone.

## Immediate next action

Deploy latest branch and run:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== LIZARD RULE SENSITIVITY ====="
docker compose exec -T backend \
  python -m app.scripts.combat_lizard_rule_sensitivity
```

Paste the complete output back to the development chat.

After that:

1. if real Lizard-sensitive cases exist, promote stable sample references into targeted regression fixtures/checks where appropriate;
2. if none exist, record Lizard race coverage as present but special endurance branch unexercised by the current corpus;
3. then evaluate Federation combat-start transformations that are directly observable without assuming full optional weapon loadout;
4. investigate right-balance only with evidence that isolates combat mass from changing load, not `hull mass + 360` guessing;
5. preserve Federation between-fight recovery, no-starbase multi-wave carry and starbase hidden-state gaps as explicitly unvalidated/fail-closed;
6. once combat validation is materially closed, continue movement fuel model, then Tow before Move Most/Intercept.

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
