# Planets Intel — Current Handoff

Updated: 2026-08-25 22:25 +03:00

GitHub is the source of truth. Active development remains on `feature/operational-ui`. A fresh chat must read this file together with `NEW_CHAT_START.md`, `PROJECT_STATE.md` and `BATTLE_PLANNER_HANDOFF_2026-08-25.md`, then inspect the actual branch HEAD and `/opt/planets-intel` before deploying.

## Repository / runtime

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production backend image embeds the React/Vite frontend.
- Do not infer server HEAD from chat history; inspect it before every deploy.

## Battle Planner UX checkpoint — runtime validated

The 2026-08-25 Battle Planner picker/editor work has now been browser-validated by the user and should no longer be treated as pending runtime validation.

Confirmed in the deployed UI:

- the old huge combined combatant dropdown is gone;
- LEFT/RIGHT use separate `Known ships`, `Known planets`, and `Generic ship / planet` sources;
- known ships are grouped by race;
- low-armament support ships are hidden by default and restored by `Show support ships`;
- `VIRGO CLASS BATTLESTAR #19` can edit simulated installed beams from a zero-start setup up to factual hull capacity;
- at least one second zero-installed / positive-capacity hull was also validated;
- generic ships work;
- generic planets/starbases on RIGHT work and open in the editor;
- multiple LEFT/RIGHT combatants work;
- queue reordering works;
- side swapping works;
- deterministic and odds paths work in normal validation cases;
- the VCR-derived validation-lab spacing and compact starbase toggle layout were visually rechecked and accepted.

Hard semantic invariants remain unchanged:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Editing a Battle Planner loadout is a simulation assumption and must not mutate factual intel.

## Battle Planner cleanup completed

The old combined-picker dead state/helper code was removed after runtime confirmation:

```text
shipKeys
leftAddKey
rightAddKey
addCombatant(...)
AddCombatantRow
```

Default queue initialization semantics were preserved.

Generic hull selection is now grouped using factual rule-catalog race hull membership (`hulls` / `basehulls`) rather than name heuristics. The unnecessary `Manual ·` prefix was removed from the generic hull picker.

Relevant post-handoff implementation commits include:

```text
7238dc409a22c4e06fe6958dea24a9e2abc58044  fix: keep battle picker sources horizontal
59f923b5...                                      generic hull grouping by factual race catalog
479368e6...                                      remove redundant Manual prefix
083b4424...                                      VCR validation spacing pass
a5c34fd994a0833bb96c4f7d1c167eaf89d48830  refactor: remove legacy battle picker state
2a443bf4feaaa382b618568f9e35236e3e3801a0  fix: normalize battle planner field spacing
a5f7d3022d00b591ca2dd768f562a3ede27a56ec  fix: restore VCR validation layout gutters
```

Always inspect Git history for exact intermediate SHAs rather than relying on abbreviated entries above.

## Deferred observation — Battle sequence odds 502

One browser screenshot during validation showed:

```text
Battle sequence odds failed: 502 Proxy Error
```

The UI happened to show `10000` battles at the time, but this was one observation only. It is **not established** that 10,000 battles are the cause or that there is a reproducible threshold bug.

Subsequent validation showed queue logic working with the full 118-seed series and a single deterministic run.

This investigation is explicitly deferred. When it is picked up later:

- reproduce deliberately;
- measure backend/proxy duration and logs;
- distinguish timeout vs resource exhaustion vs another failure;
- do not blindly raise proxy timeouts.

Do not spend time on this now unless the user explicitly returns to it.

## Real VCR replay regression checkpoint — runtime validated

Read-only diagnostic:

```text
backend/app/scripts/combat_regression_dump.py
```

Implementation commits:

```text
35cbd5df745e601e0d0fdad68544bc04c319134e  feat: add combat replay regression diagnostic
1755db24dedcfa89f9b73a90841b5429ec11b6ed  test: cover combat regression diagnostic helpers
```

The diagnostic scans persisted factual `CombatObservation` rows, deduplicates observer copies, detects raw-payload conflicts, replays selected factual payloads through the persisted `GameRuleCatalog`, reports exact `ReplayUnsupported` reasons, and compares replay terminal ammunition with any analyst-confirmed `CombatStateObservation` values. It performs no writes.

Production runtime result on 2026-08-25, server HEAD `84bcff2726c5b295d7843039bbb66dc113c40c9e`:

```text
stored_observations:       347
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

Per-game replay support was also complete for every stored VCR:

```text
680933  40 / 40
682909  40 / 40
682932  19 / 19
683230  22 / 22
683330  23 / 23
683335   1 / 1
```

All six catalogs reported Classic combat RNG (`combatrng = 0`).

Interpretation constraints:

- `145/145 replay_supported` means all currently stored factual VCR inputs are accepted by the current deterministic engine;
- it does **not** prove every Host special mechanic is represented in the corpus;
- the two analyst matches are genuine validation points, but two checks are not enough to claim universal terminal-state correctness;
- missing analyst confirmation is absence of independent validation, not failure;
- deterministic replay remains derived evidence, never a factual observation.

## Current development focus — factual combat corpus coverage

The next task is to determine what the 145 real VCRs actually exercise before changing combat mechanics blindly.

New read-only diagnostic:

```text
backend/app/scripts/combat_corpus_coverage.py
```

Current implementation commits after the validated server HEAD:

```text
7feb0f044ad356755505a0d7701a1c0e08c6f379  feat: add factual combat corpus coverage diagnostic
dd63791cd7cc164f919ae2a5a0df5f3433ecfe65  test: cover combat corpus classification
```

The coverage report classifies factual input shapes only. It reports:

- ship-vs-ship / ship-vs-planet shapes;
- starbase battles;
- carrier and carrier-vs-carrier cases;
- torpedo-ship cases;
- damaged/sub-full-shield combat starts;
- unarmed ships in combat;
- Federation and Lizard ship cases, including ship-vs-planet subsets;
- the factual input shape matching the current simulator right-balance eligibility predicate;
- race IDs seen in ship combat;
- hull IDs/names actually exercised;
- stable sample `(game, turn, vcr)` references for targeted follow-up.

A coverage hit means only that such an input occurred. It must not be interpreted as proof that the corresponding Host special rule was modeled correctly.

## Immediate next action

After CI for the latest branch HEAD is green, deploy and run the coverage audit:

```bash
cd /opt/planets-intel
bash scripts/deploy/production.sh

echo
echo "===== COMBAT CORPUS COVERAGE ====="
docker compose exec -T backend \
  python -m app.scripts.combat_corpus_coverage
```

Paste the complete JSON output back to the development chat.

The next implementation pass should use that output to:

1. identify special combat branches actually represented by real VCRs;
2. choose real sample VCRs for targeted regression validation;
3. distinguish unexercised mechanics from exercised-but-unverified mechanics;
4. add stable fixtures/checks where factual evidence is sufficient;
5. preserve fail-closed behavior where Host mechanics remain unknown;
6. only after the combat checkpoint is materially closed, continue to movement fuel model, then Tow resolution ahead of Move Most / Intercept.

## Communications status

True Planets.nu threaded replies remain validated and working through:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Do not reopen Communications without a new reason. Contract details remain in:

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

If the tree is clean and the server is behind:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

Do not claim runtime validation from static code or CI alone. Runtime claims require actual server/browser/diagnostic output.
