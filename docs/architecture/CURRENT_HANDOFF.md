# Planets Intel — Current Handoff

Updated: 2026-08-25 15:00 +03:00

This is the exact current handoff for a fresh development chat. GitHub is the source of truth. Read this together with `NEW_CHAT_START.md`, `PROJECT_STATE.md` and the dedicated Battle Planner handoff, then inspect the actual branch HEAD and `/opt/planets-intel` before deploying.

## Repository / branch

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production `backend` Docker image builds and embeds the React/Vite frontend.
- Server Git is old; prefer `git symbolic-ref --quiet --short HEAD`.

## Current functional checkpoint

The last Battle Planner code commit before this documentation checkpoint is:

```text
414e0bdb4a56e9235e0197f1aaa81c20b0231a20
feat: separate battle planner combatant pickers
```

Relevant current Battle Planner commits:

```text
e30bfb170b82e6df78d21daf2fd98283f01bdfb3  fix: edit weapons by hull capacity
9b2dda5b8561c882bf4225be9e9438facba8d5c7  feat: split battle planner combatant sources
414e0bdb4a56e9235e0197f1aaa81c20b0231a20  feat: separate battle planner combatant pickers
```

The branch HEAD is newer because this handoff is committed afterward. Always inspect actual GitHub HEAD rather than assuming the SHA above is branch HEAD.

Detailed Battle Planner state is frozen in:

```text
docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md
```

## Communications status

True Planets.nu game-feed replies are implemented using the verified official-client contract:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Replying to a child normalizes to `thread_root_id`; private participants are preserved and reconciliation requires the new activity to have the expected factual `parent_id`.

The user has now explicitly validated in the deployed browser UI that the Communications reply path works.

Do not reopen the old `/account/post` hypothesis without new upstream evidence. Contract details are in:

```text
docs/architecture/COMMUNICATIONS_REPLY_CONTRACT.md
```

## Current Battle Planner problem / requested UX

The old UI had one huge combatant dropdown mixing known ships and generic hulls. In a real game it was flooded with freighters and difficult to use.

Required add sources:

```text
Known ships
Known planets
Generic ship / planet
```

Additional requirements:

- Known ships grouped by race.
- Freighters/tankers/probes/support hulls hidden by default but still available on demand.
- No factual intel is deleted by picker filtering.
- Known ships must expose editable simulated weapons based on hull capacity even if current/observed setup contains zero/unknown installed weapons.
- Concrete live example: `VIRGO CLASS BATTLESTAR #19` showed `0B · 0T · 8 bays`, and the old editor did not allow configuring its lasers/beams. The user noted other hulls have the same problem.

## What is already implemented

### Weapon editor

`frontend/src/features/dashboard/BattleSimulatorEditor.tsx`

The editor now derives control availability and maxima from hull rule-catalog capacity. A beam-capable hull still shows `Installed beams` when the materialized setup begins at zero, with an explicit simulation warning.

Same principle applies to launchers and fighter bays.

### Combatant source picker

`frontend/src/features/dashboard/BattleSimulatorAddPicker.tsx`

Implemented:

- `Known ships`
- `Known planets`
- `Generic ship / planet`
- known ships grouped by owner race using `<optgroup>`;
- support-ship toggle;
- support-filter heuristic is picker-only and does not alter intel;
- known/generic planets are RIGHT-only under the current fixed-defender sequential-wave model.

Current support-ship default heuristic:

```text
show as primary combat hull when:
launchers > 0 OR bays > 0 OR beams >= 4
```

This is UI filtering only, not factual combat inference. It needs live review because specialty combat hulls with fewer than four beams and no tubes/bays could be hidden by default.

### Workbench integration

`frontend/src/features/dashboard/BattleSimulatorWorkbench.tsx`

LEFT and RIGHT now use `BattleSimulatorAddPicker`; selected combatants are materialized first and appended through `appendCombatant()`.

There is still dead legacy state/helper code from the old combined picker (`leftAddKey`, `rightAddKey`, `addCombatant`, and related `shipKeys` initialization). Remove it only after runtime validation confirms the new picker behavior; do not accidentally alter default queue initialization.

## Hard semantic invariants

These must survive every Battle Planner/UI change:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
```

Additional rules:

- Editing Battle Planner loadout is a simulation assumption unless backed by factual observed data.
- A hull's capacity proves what can be installed, not what is currently installed.
- Unknown equipment must never be silently promoted to zero or factual equipment.
- VCR equipment is combat-time factual evidence and must not overwrite current state.
- Deterministic replay is derived evidence, not factual observation.
- Picker filtering is presentation only; it must never remove stored intel.

## Immediate next actions

1. Read, in order:
   - `docs/architecture/NEW_CHAT_START.md`
   - `docs/architecture/PROJECT_STATE.md`
   - `docs/architecture/CURRENT_HANDOFF.md`
   - `docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md`
2. Inspect actual GitHub HEAD of `feature/operational-ui`.
3. Inspect `/opt/planets-intel` branch/HEAD/dirty state/divergence.
4. If safe, deploy current branch with `scripts/deploy/production.sh`.
5. Browser-validate Battle Planner:
   - old giant combined dropdown gone;
   - three source selectors visible;
   - known ships grouped by race;
   - support ships hidden by default and restored by toggle;
   - Virgo #19 exposes beam controls up to hull capacity despite a zero-start setup;
   - test at least one second affected hull;
   - generic ship and generic planet/starbase still work;
   - queue and combat behavior unchanged.
6. Fix actual runtime/UI regressions found during that validation.
7. Clean obsolete combined-picker state after behavior is confirmed.
8. Add focused tests for picker grouping/filtering and hull-capacity editor visibility if the existing frontend test setup supports it cleanly.

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

If the tree is clean and the server is behind:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

Do not claim runtime validation unless the user has shown the server/deploy/browser result.

## New-chat bootstrap

A fresh chat should not reconstruct state from old conversation memory. It should read the four files listed above, inspect actual GitHub HEAD, and continue from the Battle Planner runtime validation task.
