# Planets Intel — Current Handoff

Updated: 2026-08-25 20:35 +03:00

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

## Current development focus — real VCR combat regression coverage

The next active task is no longer picker UI work. It is systematic combat-model validation against stored real VCR evidence before moving back to movement/fuel/Tow.

New read-only diagnostic:

```text
backend/app/scripts/combat_regression_dump.py
```

Implementation commits before this documentation update:

```text
35cbd5df745e601e0d0fdad68544bc04c319134e  feat: add combat replay regression diagnostic
1755db24dedcfa89f9b73a90841b5429ec11b6ed  test: cover combat regression diagnostic helpers
```

The diagnostic:

- scans persisted factual `CombatObservation` rows;
- deduplicates one VCR observed through multiple linked accounts;
- reports raw-payload conflicts between observers instead of reconciling them silently;
- replays each selected factual payload through the current persisted `GameRuleCatalog`;
- reports exact `ReplayUnsupported` reasons rather than skipping them silently;
- reports deterministic terminal state for supported VCRs;
- compares replay post-combat torpedo/fighter values with any stored `CombatStateObservation` analyst confirmations;
- treats missing analyst confirmation as absence of validation, not failure;
- performs no writes.

The existing production `combat_replay_state` path continues to fail closed and is not changed by this diagnostic.

## Immediate next action

After CI is green, sync/deploy the latest branch and run the read-only diagnostic inside the production backend container.

Server block:

```bash
cd /opt/planets-intel

bash scripts/deploy/production.sh

echo
echo "===== COMBAT REGRESSION ====="
docker compose exec -T backend \
  python -m app.scripts.combat_regression_dump
```

Paste the complete JSON output back to the development chat. The default output includes all summary statistics but only details for interesting cases (`unsupported`, payload conflicts, analyst mismatches/not-comparable). Use `--all` only when a later investigation needs every supported replay.

The next implementation pass should then:

1. classify all unsupported reasons from real persisted VCRs;
2. separate genuinely unsupported Host modes from missing/incorrect adapter data;
3. turn confirmed real regression cases into stable fixtures where practical;
4. fix only mechanics supported by rule/catalog or factual evidence;
5. preserve fail-closed behavior for unknown Host mechanics;
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
