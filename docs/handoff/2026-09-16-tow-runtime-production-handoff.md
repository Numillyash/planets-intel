# 2026-09-16 — Tow runtime / production handoff

GitHub is the source of truth. This document records the runtime state reached at the end of the 2026-09-16 chat; a fresh chat must still inspect the actual branch/server HEAD before making current-state claims.

## Repository / branch

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Production deploy entrypoint: `scripts/deploy/production.sh`
- Adjacent research repository: `Numillyash/planets-lab`, branch `main` (inspect actual HEAD before use)

## Production checkpoint

Production was successfully deployed at:

```text
2c8f0a9c0d18b800b743436aa6ba980dfc7b0a52
```

Deploy result supplied from the production host:

```text
Build: OK
Backend tests: OK (300)
DB before/target/after: 0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
Log: /opt/planets-intel/logs/deploy/20260916-173106-production.log
```

This SHA is PR #16 merged into `feature/operational-ui` (`fix: render unresolved factual Tow context`). Documentation-only commits made after this handoff do not imply a newer production deploy.

## Tow runtime findings now established

### Factual Tow is no longer lost when there is no local draft

The production movement-prediction facade was corrected so factual Tow participants are emitted even when no `ShipOrderDraft` exists. This closed the earlier bug where the runtime knew about factual Tow but the API serialized only draft-backed rows.

The diagnostic path was also corrected to use the effective prediction facade and the real `tow_tower_ship_id` field, so it no longer falsely reports an empty prediction set merely because the Tow came from factual orders.

### Beta Auriga / helping die / Eros #79

Concrete runtime case:

```text
game_id=684653
linked_account_id=2
turn=29
ship #79 EROS CLASS RESEARCH VESSEL
mission=6
mission1target=63
warp=8
origin=(2254,1861)
waypoint=(2252,1854)
```

The private factual snapshot therefore contains the real upstream Tow order. The Planets.nu -> private sync -> factual DB path is not the reason this Tow disappeared previously.

After the API fix, factual Tow produces both the tower and towed-target prediction rows. However, the final endpoint remains intentionally UNKNOWN in the current case because the known pre-well Tow endpoint enters a planetary warp well and the Tow + planetary-warp-well interaction is not independently promoted as a final production rule for that dependency path.

The frontend renderer was therefore changed to render bounded unresolved Tow context rather than hide the row entirely. For such cases it may show the known pre-well leg and an explicit unknown final state, e.g. `TOW PRE-WELL · FINAL ?`, `TOWED PRE-WELL · FINAL ?`, plus the unresolved well dependency. It must not invent a final coordinate.

### Lizard Class Cruiser #33

In the exact diagnostic snapshot used during this chat:

```text
game_id=684653
linked_account_id=2
turn=29
ship #33 LIZARD CLASS CRUISER
mission=8
mission1target=0
draft=null
```

Therefore the absence of `PREDICTED TOW` for LCC in that captured backend state was not proven to be a renderer failure: there was no persisted Tow draft for #33 at inspection time.

Next browser/runtime acceptance must explicitly:

1. set Tow on #33;
2. select the intended target;
3. click `Save draft`;
4. immediately rerun `bash scripts/maintenance/inspect-tow-orders.sh 33 79`;
5. verify whether #33 now has a persisted draft and prediction rows.

If #33 is still `draft:null` after an explicit successful Save action, treat that as a separate draft-persistence/save-path defect and debug the save API / snapshot binding / DB path. Do not reopen the map renderer first.

## Current evidence boundaries

Keep these boundaries intact:

- factual observation != local draft != prediction != analyst inference;
- snapshot neutronium != automatically Tow-phase neutronium;
- known Tow lock does not imply a known final endpoint when an earlier dependency is unresolved;
- unresolved special interactions must fail closed;
- showing a known partial/pre-dependency path is acceptable only when the UI labels the final state unknown.

The base finite-fuel Tow fuel/mass semantics remain supported by `planets-lab`, including the post-Alchemy combined tower+towed mass discriminator and proportional insufficient-fuel movement. Special ordering/interactions remain separately scoped.

## Immediate next actions

1. Browser-check Eros #79 after the 2c8f0a9 production deploy. Confirm factual Tow is now visible without creating a local draft and that unresolved warp-well context is labelled as unknown rather than silently omitted.
2. Reproduce LCC #33 with an explicit Save draft, then immediately run:

```bash
cd /opt/planets-intel
git pull --ff-only origin feature/operational-ui
bash scripts/maintenance/inspect-tow-orders.sh 33 79
```

3. If LCC remains `draft:null`, debug persistence. If the draft exists but the prediction row is absent, debug prediction construction. If both exist but the map is blank, only then return to renderer debugging.
4. After this acceptance, continue IntelBoard product work using real blocker populations / analyst-threat UX rather than waiting for complete NuHost combat reconstruction.

## Fresh-chat bootstrap

Read, in order:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. `docs/handoff/2026-09-16-tow-runtime-production-handoff.md`

Then inspect actual GitHub HEAD and server state. Never assume the checkpoint SHA above is still the current branch HEAD.
