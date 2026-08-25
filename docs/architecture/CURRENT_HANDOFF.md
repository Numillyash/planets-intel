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
HEAD:       db1fec23715f4bda111d619daaa678cce9048cad
BUILD:      OK
TESTS:      OK — 214
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

Read-only detailed diagnostic:

```text
backend/app/scripts/combat_corpus_coverage.py
```

It classifies factual VCR input shapes without asserting that a Host special rule fired. The implementation preserves `unknown != zero` and reports race/hull/sample coverage.

Observed corpus includes substantial carrier combat and multiple relevant hull families, including Virgo, Rush, Gorbie, Golem, Lizard Cruiser, Firecloud, Biocide, Kittyhawk and others. Coverage hits are evidence that those inputs occurred, not proof of their special mechanics.

Because the full report is too large for routine chat handoff, a compact projection was later added:

```text
backend/app/scripts/combat_corpus_summary.py
```

It reuses the exact same classifier and only removes samples/hull detail from the output. It introduces no second combat classification path.

## Real multi-VCR ship carryover — runtime validated

Read-only diagnostic:

```text
backend/app/scripts/combat_chain_regression.py
```

Runtime found:

```text
unique_vcrs:                          145
replay_supported:                     145
ship_appearances:                     206
candidate_same_turn_ship_chains:       23
same_location_transitions:             42
skipped_location_change:                0
reappearance_after_defeat:              0
federation_race_transitions:            0
non_federation_shield_rule_matches:    42
non_federation_shield_rule_mismatches:  0
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

The first runtime JSON incorrectly printed public `matches: 0` / `mismatches: 0` because summary aggregation compared statuses `match` / `mismatch` directly with public keys `matches` / `mismatches`. The comparison logic itself was correct. This diagnostic-only bug was fixed and regression-tested.

### Federation boundary

The real chain corpus currently contains:

```text
federation_race_transitions: 0
```

Therefore the Battle Planner Federation shield-recovery-between-fights rule is **not yet empirically validated by a real repeated Federation VCR chain**. Keep it as a documented/modelled rule, not a claimed corpus validation.

## Real planet / starbase multi-wave carryover — runtime checked

Read-only diagnostic:

```text
backend/app/scripts/combat_planet_chain_regression.py
```

Production runtime on server HEAD `db1fec23715f4bda111d619daaa678cce9048cad` found:

```text
unique_vcrs:                          145
replay_supported:                     145
planet_appearances:                    84
candidate_same_turn_planet_chains:      1
same_location_transitions:              1
matches:                                1
mismatches:                             0
shield_matches:                         1
shield_mismatches:                      0
no_starbase_exact_matches:              0
no_starbase_exact_mismatches:           0
no_starbase_exact_not_comparable:       0
starbase_or_unknown_transitions:         1
```

The only repeated factual planetary defender is:

```text
game 682909
turn 9
planet #75 — Launa Planet
VCR 9 -> VCR 10
has_starbase = true
terminal shield 0 -> next factual start shield 0
```

Interpretation:

- direct planetary shield carry is confirmed for this single starbase transition;
- there are **no real repeated no-starbase planet chains** in the current corpus, so exact DP/fighter/beams/bays/mass carry has not been empirically validated from real VCR chains;
- persistent starbase defense/fighters/tech/accumulated-damage state remains intentionally fail-closed because VCR data does not uniquely expose those values;
- do not weaken that boundary or invent starbase state from the one observed transition.

Current Battle Planner exact planet model in `battle_simulator_planet.py` remains unchanged: it carries/rebuilds drained shield, planet defense-post damage, generated planetary fighter losses, starbase fighters before planetary fighters, and re-derived combat properties only where the required state is factual or exactly derivable.

## Current development focus — compact special-combat coverage triage

The next step is to use the stored VCR corpus to decide which special combat branches can be validated with real examples before changing any combat mechanics.

Latest compact diagnostic commits:

```text
1d86dec886525377babb8bef1a8966f2c8638814  feat: add compact combat corpus summary
c08db2afca9dc7756bffaa7720adb02855a571d5  test: cover compact combat corpus summary
```

The compact report contains only:

- corpus summary;
- battle shape counts;
- special-mechanic input counts;
- compact per-race counts.

It deliberately omits hull/sample detail already available from the full coverage report.

## Immediate next action

Deploy the latest branch and run the compact corpus summary:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== COMBAT CORPUS SUMMARY ====="
docker compose exec -T backend \
  python -m app.scripts.combat_corpus_summary
```

Paste the complete output back to the development chat.

Use that output to select the next autonomous real-data regression target. Preserve these already-established evidence gaps:

- Federation between-fight recovery: no real repeated Federation chain;
- exact no-starbase planet multi-wave carry: no real repeated no-starbase chain;
- starbase persistent post-damage state: not uniquely derivable from VCR, fail closed.

Only after the combat checkpoint is materially closed should development return to movement fuel model, then Tow resolution ahead of Move Most / Intercept.

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
