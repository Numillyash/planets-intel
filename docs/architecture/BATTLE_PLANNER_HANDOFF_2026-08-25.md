# Battle Planner handoff — 2026-08-25

This file is the exact handoff for the Battle Planner work started at the end of the previous development chat.

GitHub is the source of truth. Continue on `Numillyash/planets-intel`, branch `feature/operational-ui`.

## Code checkpoint before this handoff

The Battle Planner implementation checkpoint is:

```text
414e0bdb4a56e9235e0197f1aaa81c20b0231a20
feat: separate battle planner combatant pickers
```

The handoff/documentation commits written after it will advance branch HEAD. Do not confuse the documentation HEAD with the last functional Battle Planner code commit.

Relevant implementation commits, in order:

```text
e30bfb170b82e6df78d21daf2fd98283f01bdfb3  fix: edit weapons by hull capacity
9b2dda5b8561c882bf4225be9e9438facba8d5c7  feat: split battle planner combatant sources
414e0bdb4a56e9235e0197f1aaa81c20b0231a20  feat: separate battle planner combatant pickers
```

## User-reported Battle Planner problems

The previous deployed/browser UI had one huge combatant dropdown containing known ships and generic hulls together. In a real game this was dominated by freighters and made combat ships hard to find.

The requested UX is three explicit sources:

```text
Known ships
Known planets
Generic ship / planet
```

Additional requirements from the live screenshots / browser validation:

1. Known ships must be separated/grouped by race.
2. The default known-ship picker should not be flooded with freighters, tankers, probes and other obvious support ships.
3. Support ships must not be deleted from factual intel; they should merely be hidden from the default picker and remain accessible on demand.
4. A known ship can have an observed setup with no disclosed/installed beams even when the hull itself has beam capacity. The editor must still allow the analyst to configure an explicit simulated loadout.
5. Concrete live example: `VIRGO CLASS BATTLESTAR #19` displayed `0B · 0T · 8 bays`; the old editor did not expose beam/laser controls. The user noted Virgo is not the only affected hull.

## Implemented in `e30bfb1` — weapon editor by hull capacity

File:

```text
frontend/src/features/dashboard/BattleSimulatorEditor.tsx
```

The ship editor now derives physical weapon capacity from the hull rule catalog rather than deciding whether an editor control exists only from the current observed/materialized setup.

For beams, launchers and fighter bays it computes:

```text
capacity = max(current setup physical count, catalog hull capacity)
```

Consequences:

- If the hull supports beams but the current setup contains `0`, the `Installed beams` control is still shown.
- Same principle for torpedo launchers and fighter bays.
- Input maxima are constrained to the actual hull capacity instead of hard-coded 10/30 values.
- The UI shows both effective weapons and hull capacity.
- A zero currently installed count on a capable hull produces an explicit simulation warning rather than silently removing the control.

This is intentionally a simulation editor capability. It must not reinterpret unknown equipment as factual equipment.

Hard invariant:

```text
known zero != unknown
fact != inference != simulation
```

Changing `Installed beams`, technology, launchers, torpedoes, bays or fighters in Battle Planner changes only the simulated combatant.

## Implemented in `9b2dda5` — separate add sources

New file:

```text
frontend/src/features/dashboard/BattleSimulatorAddPicker.tsx
```

The picker contains three top-level source buttons:

```text
Known ships
Known planets
Generic ship / planet
```

### Known ships

Known ships come from `intel.ships` and are rendered in `<optgroup>` groups by the current canonical owner race from `game.players`.

The group label is the race label from the rule catalog. If owner/race cannot be resolved, the ship is placed under:

```text
Unknown owner / race
```

Within each race group ships are sorted by ship id.

### Support-ship filtering

A picker-only heuristic hides low-armament support hulls by default:

```text
primary combat hull if:
launchers > 0
OR fighter bays > 0
OR beams >= 4
```

The UI exposes:

```text
Show support ships (freighters, tankers, probes and other low-armament hulls)
```

Important: this is UI filtering only. It does not alter factual intel, observations, rule data or simulation mechanics.

This heuristic needs live review. It is deliberately conservative in implementation scope, but it can still hide specialty combat-capable hulls with fewer than four beams and no launchers/bays. If real games expose such useful ships, improve the picker classification using factual hull/rule metadata or a better explicit role rule. Do not turn this picker heuristic into combat inference.

### Known planets

Known planets come from `intel.planets`.

The current sequential-wave model keeps planets/starbases as fixed defenders on RIGHT, therefore `Known planets` is disabled on LEFT.

### Generic ship / planet

Generic ship mode selects any hull from the rule catalog and materializes a manual simulation combatant.

Generic planet/starbase creates a blank assumption-driven planet setup and is currently RIGHT-only for the same fixed-defender reason.

Generic planet defaults are simulation assumptions and carry an explicit warning.

## Implemented in `414e0bd` — Workbench integration

File:

```text
frontend/src/features/dashboard/BattleSimulatorWorkbench.tsx
```

Both LEFT and RIGHT add rows now use `BattleSimulatorAddPicker` and append a fully materialized combatant via `appendCombatant()`.

The explanatory text now explicitly says that combatants are added from separate Known ships / Known planets / Generic sources and that low-armament support ships are hidden by default.

## Known cleanup / review point

`BattleSimulatorWorkbench.tsx` still contains legacy add-picker state and helper code from the old combined selector:

```text
shipKeys
leftAddKey
rightAddKey
addCombatant(...)
```

The new UI no longer calls `addCombatant()` and the old add-key state is no longer needed for the picker itself. The current TypeScript config does not enable `noUnusedLocals`, so this does not necessarily break the build, but the next chat should remove dead legacy state after confirming that no initialization behavior depends on it.

Do this as cleanup only; do not change default queue initialization semantics accidentally.

## Runtime validation still required

The three Battle Planner commits above were written at the end of the previous chat and have not yet been confirmed by the user in the new picker/editor UI.

After syncing/deploying the branch, validate in the browser:

1. The old giant combined dropdown is gone.
2. LEFT and RIGHT each show the three source buttons (with planet modes disabled on LEFT as designed).
3. `Known ships` are grouped by race.
4. Freighters/support ships are hidden by default.
5. Enabling `Show support ships` restores them.
6. A known `VIRGO CLASS BATTLESTAR #19` can expose and edit installed beam count up to its hull capacity even if its materialized setup starts with `0` beams.
7. Repeat item 6 with at least one other affected hull.
8. Editing the loadout changes only the simulation combatant; factual intel must remain unchanged.
9. Generic ship and generic planet/starbase still materialize and can be edited.
10. Sequential LEFT/RIGHT queue behavior and existing VCR deterministic engine results remain unchanged.

## Deferred observation — Battle sequence odds 502

During browser validation on 2026-08-25, one screenshot showed:

```text
Battle sequence odds failed: 502 Proxy Error
```

At the time the Battle Planner `BATTLES` field was set to `10000` and the scenario used queued/multi-combatant simulation. This is only a single observed failure. It has **not** been established that `10000` battles are the cause, that the failure is reproducible, or that the threshold is specifically related to battle count.

Subsequent user validation confirmed that the queue logic itself works for the 118-seed series and for a single deterministic run. Therefore do **not** treat this as a confirmed `10k simulations` bug.

Deferred future work, only when explicitly picked up again:

- reproduce the 502 deliberately;
- identify whether it originates in reverse-proxy timeout, backend request duration, resource exhaustion, or another path;
- measure request duration and backend/proxy logs before changing limits or timeouts;
- do not mask the issue by blindly increasing proxy timeout.

The user explicitly deferred investigation for now.

## Communications checkpoint from the same session

Immediately before Battle Planner work, true Planets.nu threaded replies were implemented for Communications using the verified official game client contract:

```text
POST /game/sendmessage
parentid=<thread root activity id>
```

Replying to a child normalizes to the factual `thread_root_id`; private recipient sets are preserved and reconciliation requires the newly observed activity to have the expected factual `parent_id`.

The user has now explicitly reported that this Communications reply path works in the deployed UI.

Do not reopen the old hypothesis about a separate `/account/post` game-message reply endpoint unless new upstream evidence contradicts the captured official-client behavior.

See:

```text
docs/architecture/COMMUNICATIONS_REPLY_CONTRACT.md
```

## Immediate next actions for a new chat

1. Read:
   - `docs/architecture/NEW_CHAT_START.md`
   - `docs/architecture/PROJECT_STATE.md`
   - `docs/architecture/CURRENT_HANDOFF.md`
   - this file.
2. Inspect actual GitHub HEAD of `feature/operational-ui`.
3. Inspect `/opt/planets-intel` branch, HEAD, dirty state and divergence before deploying.
4. Deploy current branch with the repository production deploy script if the server is clean/behind.
5. Browser-validate the three Battle Planner changes listed above, beginning with Virgo #19.
6. Fix any actual runtime/UI regressions found during that validation.
7. Remove legacy combined-picker state only after functional behavior is confirmed.
8. Add focused frontend/unit coverage for picker grouping/filtering and hull-capacity editor visibility if the existing frontend test setup supports it cleanly.

## Server commands

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

Do not claim runtime validation until the user pastes the deploy/browser result.
