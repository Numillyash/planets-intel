# 2026-09-18 — Tow UX production acceptance and next blocker audit

GitHub remains the source of truth. This handoff records the production/runtime
state after the resolved Tow label cleanup and closes the remaining Tow browser
acceptance item under the revised one-label UX.

## Production runtime

Production was successfully deployed at:

```text
fd3312e75756c416dee7d9febffad2149643d5c3
```

Deploy result from `/opt/planets-intel`:

```text
Build: OK
Backend tests: OK
Ran 300 tests
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after:  0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
Log: /opt/planets-intel/logs/deploy/20260918-023940-production.log
```

No database migration was required.

## Tow browser acceptance

The production map was visually checked after the deployment above.

Observed on the acceptance screenshot:

- two distinct resolved Tow pairs were visible;
- each pair retained the amber Tow prediction geometry;
- each pair showed exactly one text label:
  `PREDICTED TOW · 81.0 ly · W9`;
- the target-side duplicate `PREDICTED TOWED` label was no longer present.

This is the intended renderer-only UX after PR #19. The target prediction row is
still rendered geometrically; only its duplicate text label is suppressed.

The earlier 2026-09-12 acceptance requirement to display both
`PREDICTED TOW` and `PREDICTED TOWED` separately is therefore superseded by
the accepted one-label-per-Tow-pair presentation.

## Tow acceptance state

The explicit Tow-target workflow is now closed for the currently scoped product
acceptance:

- explicit Tow target selection/save: PASS;
- drafted-target precedence in the acceptance case: PASS;
- mission switching / Tow-specific editor clearing: PASS;
- Tow + Intercept UI mutual exclusion: PASS;
- factual Tow visibility without a local target draft: PASS;
- unresolved Tow remains fail-closed where dependencies are unresolved: PASS;
- resolved Tow pair map rendering: PASS;
- duplicate target-side text suppression: PASS.

These UI results do not widen Host certainty. In particular:

```text
snapshot fuel != automatically Tow-phase fuel
known Tow participation != known final endpoint
UNKNOWN + provenance != PREDICTED
```

## Next product step

The next roadmap step is no longer another Tow renderer change. Inventory the
real current Turn Review blocker population before selecting another movement
mechanic for production transfer.

The read-only diagnostic introduced alongside this handoff is:

```text
scripts/maintenance/inspect-movement-blockers.sh
```

It audits only factual batches whose turn matches `games.current_turn`, calls
the same effective movement prediction facade used by production, and reports:

- predicted vs UNKNOWN rows;
- blocker counts;
- blocker × movement-phase counts;
- status and fuel-status counts;
- bounded concrete samples per blocker class;
- per-game summaries and runtime errors.

Use that output to distinguish:

- `implementation_gap`: evidence-backed candidate for product integration;
- `phase_state_required`: supported formula but missing phase-aligned factual state;
- `unsupported_host_rule`: research boundary, not a safe implementation target;
- `dependency_unresolved`, `order_ambiguity`, and `missing_fact`: separate
  operational/evidence problems.

Do not promote any endpoint solely because the diagnostic identifies its blocker
class.
