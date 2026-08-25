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
HEAD:       84aa60c26b2bc8db4644c379481bebba0a5fcafe
BUILD:      OK
TESTS:      OK — 223
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

Later GitHub commits exist for Lizard regression baselines and Federation evidence diagnostics. Do not invent a server HEAD for those until a fresh deploy output is supplied.

## Hard invariants

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Battle Planner loadout edits are simulation assumptions only. Deterministic replay is derived evidence, never a factual observation.

## Battle Planner UX / intel checkpoint — closed

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

Two intel-boundary regressions were also fixed and browser-accepted:

1. non-owner private tactical zero placeholders no longer override factual shared owner configuration;
2. existing current known ships can now receive missing immutable equipment from accessible VCR evidence, and latest-Host post-combat mutable state can be used as a simulator default without mutating canonical current intel.

Relevant commits:

```text
43ee7067925bfe6c9c82d24b454794539a48ba55  fix: reject hidden enemy loadout zero placeholders
09dc97e6f5207cb40e651aed6f0c7f423d49d678  test: cover enemy tactical zero sanitizing
3cc575086004610c31090c46d8b3549c33ea4a6e  fix: merge VCR evidence into known battle ships
84aa60c26b2bc8db4644c379481bebba0a5fcafe  fix: carry latest host combat state into planner
```

The VCR/current-state precedence remains:

```text
current factual/private/shared state
  > analyst-confirmed post-VCR state
  > deterministic replay post-VCR state
  > same-turn factual combat-start fallback
  > simulation assumption
```

For a VCR from the immediately preceding Host turn, only post-combat state is eligible; combat-start ammunition does not cross the Host boundary.

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

Validated corpus result at that checkpoint:

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

All observed game catalogs use Classic combat RNG (`combatrng = 0`). `145/145 supported` proves that stored checkpoint was accepted by the deterministic engine; it does not prove every Host special mechanic has independent factual confirmation. The store had grown to `147` unique VCRs by the later Lizard sensitivity run; the full general regression dump has not yet been rerun on those two additional VCRs.

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

Federation shield recovery between fights remains unvalidated by real repeated Federation VCRs because `federation_race_transitions = 0` at this checkpoint.

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

Runtime checkpoint counts:

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

## Lizard 150% endurance — branch exercised and regression anchored

Read-only differential diagnostic:

```text
backend/app/scripts/combat_lizard_rule_sensitivity.py
```

Latest runtime result:

```text
stored_observations:              376
unique_vcrs:                      147
lizard_vcrs:                       37
lizard_ship_side_appearances:      37
ship_vs_ship_lizard_vcrs:          30
ship_vs_planet_lizard_vcrs:         7
comparable:                         37
sensitive:                          15
insensitive:                        22
outcome_changed:                     0
terminal_only_changed:              15
ship_vs_ship_sensitive:             14
ship_vs_planet_sensitive:            1
```

Interpretation:

- the Lizard endurance branch is materially exercised by real factual inputs;
- in this corpus it changes terminal combat state in 15/37 comparable fights but does not change the winner in any of those 15;
- this is branch-exercise evidence, not by itself independent proof that every internal Host step is reproduced correctly.

Strong anchored case:

```text
game 680933 · turn 42 · VCR 201
T-REX CLASS BATTLESHIP vs VIRGO CLASS BATTLESTAR

factual race-2 replay survivor Virgo:
shield=0 damage=12 crew=1724 fighters=39

neutralized-Lizard counterfactual survivor Virgo:
shield=0 damage=9 crew=1732 fighters=42
```

The factual survivor state above is independently anchored by VCR `202`, whose factual start state exactly matches the VCR `201` terminal values.

A second keyed baseline uses game `680933`, turn `43`, VCR `216`, where the Lizard T-Rex is on RIGHT, so regression coverage is not left-side-only.

Targeted runtime regression:

```text
backend/app/scripts/combat_lizard_regression.py
```

Commits:

```text
a35efb843fbe1b918b9f25d6ac9883b7f9ec17a7  test: add factual Lizard runtime regression baselines
ef208e0de5e4ce80b1c1da24c9e0b9e8eb5965e0  test: cover Lizard runtime regression helpers
```

These keyed baselines are derived regression expectations over factual stored VCR inputs. They do not turn deterministic or counterfactual output into new factual observations.

## Current development focus — Federation directly observable combat evidence

The next roadmap target is Federation combat behavior. The current Battle Planner sequence model has three relevant Fed branches:

- damaged ships retain full effective weapon availability;
- carriers receive +3 effective fighter bays;
- surviving Fed ships recover 25% of missing shield between sequential fights, capped by damage.

The last rule still requires a repeated same-turn Federation combat chain and must remain explicitly unvalidated if none exists.

New read-only evidence audit:

```text
backend/app/scripts/combat_federation_rule_evidence.py
```

It deliberately does not infer hidden installed weapons. It reports:

- factual damaged-start Federation VCRs;
- a direct damaged-weapon signal only when factual effective beam/launcher count exceeds the normal non-Fed damage limit;
- direct `hull fighter bays + 3` comparison for the factual Fed carrier case;
- repeated same-turn/same-location Federation transitions, if any, for later shield-recovery validation.

Commits:

```text
cff2045ab6e78ea7f35967272ac2126ef3edcaa5  feat: add Federation combat rule evidence diagnostic
c2f4f9884106c36f2f6092a375cb71e7d50d99f3  test: cover Federation evidence diagnostic helpers
```

Right-side carrier balance remains intentionally later: simple `VCR mass - hull mass` is confounded by ship load/ammunition, so do not claim +360 factual validation from hull mass alone.

## Immediate next action

Deploy latest branch and run both compact checks in one server interaction:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== LIZARD REGRESSION ====="
docker compose exec -T backend \
  python -m app.scripts.combat_lizard_regression

echo
echo "===== FEDERATION RULE EVIDENCE ====="
docker compose exec -T backend \
  python -m app.scripts.combat_federation_rule_evidence
```

Paste the complete output back to the development chat.

After that:

1. if keyed Lizard regressions match, treat Lizard branch regression anchoring as closed;
2. classify directly observable Federation evidence and keep non-comparable branches explicit;
3. investigate right-balance only with evidence that isolates combat mass from changing load, not `hull mass + 360` guessing;
4. preserve Federation between-fight recovery, no-starbase multi-wave carry and starbase hidden-state gaps as explicitly unvalidated/fail-closed unless new evidence appears;
5. once combat validation is materially closed, continue movement fuel model, then Tow before Move Most/Intercept.

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
