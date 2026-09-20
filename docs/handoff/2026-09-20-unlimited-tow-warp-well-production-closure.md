# 2026-09-20 — Unlimited-fuel Tow warp-well production closure

GitHub remains the source of truth.

## Production deploy

Production was successfully deployed at:

```text
88a420d334710b6e756f10b52d35a2c303846bdc
```

Runtime result:

```text
Build: OK
Backend tests: OK
Ran 306 tests
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after:  0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
Log: /opt/planets-intel/logs/deploy/20260920-122950-production.log
```

No migration was required.

## Post-deploy blocker audit

The read-only current-turn blocker inventory was rerun after deploy.

Result:

```text
current_factual_groups        31
groups_with_prediction_items  14
groups_with_errors             0
prediction_items              48
predicted_items               48
unknown_items                  0
```

Phase population:

```text
tow:tower  24
tow:target 24
```

Status population:

```text
locked 24
towed  24
```

Blocker state:

```text
blocker_counts       {}
blocker_phase_counts {}
samples_by_blocker   {}
```

All 48 rows remained `fuel_status=unlimited`.

The previous seven Tow pairs blocked by the production Tow + planetary
warp-well guard therefore moved from UNKNOWN to PREDICTED exactly as intended.
No overlapping-well ambiguity was present in the current runtime population.

## Acceptance

The bounded transfer is accepted in production:

```text
strict deterministic Tow
+ unlimited-fuel game
+ ordinary unambiguous planetary warp well
=> shared post-well endpoint for tower and target
```

The following boundaries remain unchanged:

- finite-fuel Tow requires factual phase-aligned fuel/mass state;
- Tow contests/chains/cycles remain outside the strict subset;
- unresolved Four Fingers fuel predicates remain fail-closed;
- overlapping planetary wells remain fail-closed;
- mine/web/storm/Chunnel/hyperjump and other special interaction ordering remain separately scoped;
- movement prediction remains derived and `host_final: false`.

## Next product direction

The current emitted movement blocker population is clean. Do not use this as
evidence that every possible stored movement state is solved; this diagnostic
only measures rows currently emitted by the effective prediction facade.

The next production work should therefore leave Tow mechanics alone absent a
concrete regression and continue the roadmap into analyst/threat UX, reusing
existing factual, VCR, military-score and inference provenance rather than
inventing new state.
