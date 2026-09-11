# Turn Review blocker provenance — production runtime

Date: 2026-09-11

## Scope

This handoff records the production deployment of the first Turn Review movement-uncertainty provenance pass. It does not promote any previously uncertain movement endpoint to a deterministic prediction.

GitHub remains the source of truth. Inspect the actual `feature/operational-ui` HEAD before making current-code claims.

## Source commit

Merged source commit:

```text
d93fce4df17d25376f7c98ac98eed02253ce68f4
```

Merge title:

```text
feat: expose movement uncertainty provenance
```

The exact merged HEAD passed GitHub Actions CI before production deployment.

## Production deployment

The server deployment completed successfully at the exact source SHA above:

```text
HEAD: d93fce4df17d25376f7c98ac98eed02253ce68f4
Build: OK
Backend tests: OK
Ran 289 tests
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after:  0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
```

Production deploy log:

```text
/opt/planets-intel/logs/deploy/20260911-223653-production.log
```

No database migration was required.

## What is now deployed

Turn Review keeps factual observation evidence, local planning state and derived prediction separate and now adds structured provenance for an uncertain movement row.

The production blocker classes are:

```text
phase_state_required
implementation_gap
missing_fact
dependency_unresolved
order_ambiguity
unsupported_host_rule
```

Semantics:

- `phase_state_required`: the movement formula is supported, but the factual state required at the relevant Host phase is unavailable;
- `implementation_gap`: a lab-supported mechanic has not yet been integrated safely into the production path;
- `missing_fact`: a required factual input is missing/unknown and is not replaced by zero;
- `dependency_unresolved`: an earlier movement result required by this row is unresolved;
- `order_ambiguity`: ordering, lock precedence or target selection is ambiguous;
- `unsupported_host_rule`: the applicable Host behavior remains outside the supported production model.

This metadata is explanatory only. The rule remains:

```text
UNKNOWN + blocker provenance != PREDICTED
```

## Reconciled movement evidence wording

### Finite-fuel Intercept

The historical `planets-lab` evidence supports the finite-fuel Intercept formula. Production nevertheless withholds the endpoint because current snapshot neutronium is not automatically the factual Intercept-phase fuel state.

Therefore this case is now represented as:

```text
blocker_class = phase_state_required
fuel_basis    = deferred_until_intercept_phase_fuel
```

It is no longer described as if the formula itself were unverified.

### True-partial normal Move Most

`planets-lab` supports the continuous nominal one-turn fuel basis for true-partial normal movement as:

```text
CORPUS_OBSERVED + TESTED + DIFF_VERIFIED
```

The lab implementation charges the geometrically partial route for the continuous effective one-turn leg before integer endpoint rasterization. If fuel is insufficient, it prorates that one-turn leg and then applies Host major/minor-axis integer projection.

Production still has the older `unsupported_partial_waypoint` guard. It is now identified as:

```text
blocker_class = implementation_gap
```

Do not simply remove this guard. The safe production integration must preserve the exact lab-supported geometry/fuel basis and must continue to fail closed on missing factual inputs.

### Finite-fuel Tow

Base finite-fuel Tow movement in the ordinary Classic/Nu lab scope is supported as:

```text
DOCUMENTED + CORPUS_OBSERVED + TESTED + DIFF_VERIFIED
```

The supported base rule uses post-Alchemy combined tower+towed movement mass and proportional insufficient-fuel movement.

Production still fails closed when Tow-phase fuel/state is unavailable. Snapshot neutronium must not be silently promoted to Tow-phase fuel. Tow contests/chains/cycles and special interactions remain separately scoped.

## Next product work

The highest-value implementation gap now visible in the product is true-partial normal Move Most fuel handling. Before promoting it, compare the current production path against `planets-lab/src/planets_lab/sim/normal_movement.py` and preserve these exact properties:

1. partial route detection uses waypoint distance versus nominal one-turn range;
2. the pre-fuel endpoint uses Host major/minor-axis integer projection, not independent continuous-coordinate interpolation;
3. fuel cost for a true partial route uses the continuous nominal one-turn distance before rasterization;
4. positive insufficient fuel prorates that one-turn distance and then uses Host projection;
5. missing mass/fuel/engine facts remain UNKNOWN rather than zero;
6. zero-fuel and Gravitonic shortage stay separately fail-closed unless their own evidence boundary is satisfied.

After that integration passes CI, complete browser/runtime acceptance of the explicit Tow target flow. Do not deploy this documentation-only checkpoint by itself merely to make production HEAD match docs.
