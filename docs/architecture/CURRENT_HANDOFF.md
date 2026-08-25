# Planets Intel — Current Handoff

Updated: 2026-08-26

GitHub is the source of truth. Active development remains on `feature/operational-ui`. A fresh chat must read this file together with `NEW_CHAT_START.md`, `PROJECT_STATE.md` and `BATTLE_PLANNER_HANDOFF_2026-08-25.md`, then inspect the actual branch HEAD and `/opt/planets-intel` before deploying.

## Repository / runtime

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production backend image embeds the React/Vite frontend.
- Do not infer server HEAD from chat history; inspect it before every deploy.

Last explicitly runtime-confirmed deploy in this handoff:

```text
HEAD:       41430e66960c73d1bfd740d73f1b696ada8d048d
BUILD:      OK
TESTS:      OK — 210
MIGRATIONS: 0017_outgoing_msg_recipients (head)
HEALTH:     OK
```

Later GitHub commits exist after that server HEAD; inspect the actual branch before the next deploy.

## Battle Planner UX checkpoint — runtime validated

The 2026-08-25 picker/editor/UI work is browser-validated and should not be reopened as pending work.

Confirmed in deployed UI:

- separate `Known ships`, `Known planets`, `Generic ship / planet` sources;
- known ships grouped by race;
- support ships hidden by default and restored by `Show support ships`;
- zero-installed / positive-capacity hulls, including `VIRGO CLASS BATTLESTAR #19`, expose simulation weapon controls up to hull capacity;
- generic ships are grouped using factual race-catalog hull membership and no longer show the redundant `Manual ·` prefix;
- generic planets/starbases work on RIGHT and open in the editor;
- multiple LEFT/RIGHT combatants work;
- queue reorder and side swap work;
- deterministic and normal odds paths work;
- VCR-derived validation-lab spacing and compact starbase layout were visually accepted;
- legacy combined-picker state/helper code was removed without changing default queue initialization.

Hard invariants:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Battle Planner loadout edits remain simulation assumptions only.

## Deferred observation — Battle sequence odds 502

One browser screenshot showed:

```text
Battle sequence odds failed: 502 Proxy Error
```

The UI happened to contain `10000` battles, but this was one observation only. It is **not established** that 10,000 battles are the cause or that a reproducible threshold bug exists.

Queue logic was subsequently confirmed with the classic 118-seed series and a single deterministic run.

This investigation is explicitly deferred. When picked up later:

- reproduce deliberately;
- measure backend and reverse-proxy timings/logs;
- distinguish timeout, resource pressure and other failures;
- do not blindly raise proxy timeouts.

Do not spend time on this unless the user explicitly returns to it.

## Real VCR deterministic replay — runtime validated

Read-only diagnostic:

```text
backend/app/scripts/combat_regression_dump.py
```

Validated production result:

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

Per-game deterministic replay support was complete for every stored unique VCR. All observed game catalogs used Classic combat RNG (`combatrng = 0`).

Interpretation constraint: `145/145 supported` proves current stored inputs are accepted by the deterministic replay engine. It does **not** prove every Host special mechanic exists in the corpus or that every terminal state has an independent factual confirmation.

## Factual combat corpus coverage

Read-only diagnostic:

```text
backend/app/scripts/combat_corpus_coverage.py
```

It classifies factual VCR input shapes without asserting that a Host special rule fired. The implementation preserves `unknown != zero` and reports race/hull/sample coverage.

Observed corpus includes substantial carrier combat and multiple relevant hull families, including Virgo, Rush, Gorbie, Golem, Lizard Cruiser, Firecloud, Biocide, Kittyhawk and others. Coverage hits are evidence that those inputs occurred, not proof of their special mechanics.

## Real multi-VCR ship carryover — runtime validated

Read-only diagnostic:

```text
backend/app/scripts/combat_chain_regression.py
```

Runtime on server HEAD `41430e66960c73d1bfd740d73f1b696ada8d048d` found:

```text
unique_vcrs:                        145
replay_supported:                   145
ship_appearances:                   206
candidate_same_turn_ship_chains:     23
same_location_transitions:           42
skipped_location_change:              0
reappearance_after_defeat:            0
federation_race_transitions:          0
non_federation_shield_rule_matches:  42
non_federation_shield_rule_mismatches: 0
```

The actual transition records showed all 42 same-location transitions as `status = match`. For each comparable transition, deterministic terminal values became the factual next-VCR start values exactly for:

```text
damage
crew
torpedoes
fighters
shield (non-Federation cases in this corpus)
```

A particularly useful real example is game `680933`, turn `42`, Virgo ship `#10`: after VCR `201`, replay terminal `damage=12`, `crew=1724`, `fighters=39`, `shield=0` is exactly the factual start state of VCR `202`, even though the ship changes combat side.

### Diagnostic reporting bug discovered and fixed

The first runtime JSON incorrectly printed:

```text
matches: 0
mismatches: 0
```

while `match_samples` contained successful records and the shield counter showed 42 matches. The comparison logic was correct; only summary aggregation was wrong because statuses `match` / `mismatch` were compared directly with public keys `matches` / `mismatches`.

Fixed after the validated server HEAD:

```text
c79795cf103fcc265a4397db0928c3fb3244816f  fix: count combat chain regression statuses
0f36cf4883c2b25919770525eb25012d3052b926  test: lock combat chain summary counters
```

Do not reinterpret the original `matches: 0` as a combat-model failure.

### Federation boundary

The real chain corpus currently contains:

```text
federation_race_transitions: 0
```

Therefore the Battle Planner Federation shield-recovery-between-fights rule is **not yet empirically validated by a real repeated Federation VCR chain**. Keep it as a documented/modelled rule, not a claimed corpus validation.

## Current development focus — real planet / starbase multi-wave carryover

The next sequence-model layer is planetary defender carryover.

Current Battle Planner exact model in `battle_simulator_planet.py` carries/rebuilds:

- drained shield;
- planet defense-post damage;
- generated planetary fighter losses;
- starbase fighters before planetary fighters;
- re-derived beams, bays, fighters and mass.

It intentionally fails closed when a surviving starbase takes hull damage because the VCR/docs do not expose enough state to derive exact post-combat starbase defense, tech and accumulated base damage.

New read-only diagnostic added after the last confirmed server deploy:

```text
backend/app/scripts/combat_planet_chain_regression.py
```

Implementation commits:

```text
f07dc9ad03bd84fe063a87e376b6a9671588d0b3  feat: add real planet chain regression diagnostic
c75ab12902f8d80a12475feab0362bbe8f6aff4a  test: cover real planet chain diagnostic helpers
```

Diagnostic policy:

- repeated planet/starbase VCRs are grouped only within one game, turn, factual planet id and position;
- factual shield carry is checked directly for every surviving repeated planetary defender;
- exact full carry prediction is attempted only if `hasstarbase` is explicitly false;
- for a non-starbase planet, factual combat mass gives the candidate starting DP as `mass - 100`;
- that inferred state must first reproduce the factual first VCR combat setup before it is trusted;
- only then is `apply_planet_carryover()` used and compared with the next factual VCR start;
- starbase hidden state is never guessed.

## Immediate next action

Deploy the latest branch and run the planet-chain diagnostic:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== REAL PLANET COMBAT CHAINS ====="
docker compose exec -T backend \
  python -m app.scripts.combat_planet_chain_regression
```

Paste the complete output back to the development chat.

After that result:

1. fix any real no-starbase carry mismatch rather than synthetic assumptions;
2. classify starbase transitions separately and preserve fail-closed boundaries;
3. keep Federation between-fight recovery marked unvalidated until a factual repeated Federation chain exists;
4. continue targeted special-combat validation only where corpus/rule evidence exists;
5. once the combat checkpoint is materially closed, return to movement fuel model, then Tow resolution ahead of Move Most / Intercept.

## Communications status

True Planets.nu threaded replies remain validated and working through:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Do not reopen Communications without new evidence. See:

```text
docs/architecture/COMMUNICATIONS_REPLY_CONTRACT.md
```

## Server preflight for future chats

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
