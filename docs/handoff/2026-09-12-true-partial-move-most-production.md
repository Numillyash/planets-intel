# True-partial Move Most production runtime — 2026-09-12

## Scope

This handoff records the successful production deployment of the lab-verified true-partial normal-speed Move Most fuel/geometry integration in `Numillyash/planets-intel`.

GitHub remains the source of truth. The active development branch is `feature/operational-ui`; always inspect its actual HEAD before relying on this checkpoint.

## Production deployment

The server fast-forwarded from:

```text
d93fce4df17d25376f7c98ac98eed02253ce68f4
```

to:

```text
f5c9ab9bfcc3c9c5bb32f2bbf7a5f0f3340e0ced
```

The production deployment completed successfully:

```text
HEAD: f5c9ab9bfcc3c9c5bb32f2bbf7a5f0f3340e0ced
Build: OK
Backend tests: OK
Ran 296 tests in 0.224s
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after: 0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
```

Deployment log:

```text
/opt/planets-intel/logs/deploy/20260911-233730-production.log
```

No database migration was required by this mechanics transfer.

## Mechanics transferred

The production movement path now integrates the verified normal-speed true-partial semantics already established in `planets-lab`.

For a waypoint beyond one-turn range:

1. the one-turn geometric endpoint uses Host major/minor-axis integer projection rather than independently rounded continuous coordinates;
2. movement fuel is charged against the continuous nominal one-turn leg before that endpoint is rasterized;
3. when positive fuel is insufficient, the nominal one-turn leg is prorated by `fuel_available / fuel_required` and the resulting travel distance is projected with the same Host major/minor-axis algorithm;
4. the rasterized endpoint distance is not substituted as the fuel-cost basis.

The historical discriminator locked into production regression coverage is:

```text
game: 360690
turn: 164
ship: 41
origin: (1949,2950)
waypoint: (2008,3067)
warp: 9
movement mass: 517 KT
available fuel: 11 KT
nominal one-turn distance: 81 ly
nominal fuel cost: 41 KT
factual endpoint: (1959,2969)
```

The production path reproduces the factual endpoint by prorating the nominal 81-ly leg and applying Host integer projection.

## Evidence boundary

This deployment does **not** widen the supported movement scope beyond the evidence.

Still fail-closed:

- zero-fuel normal movement;
- insufficient-fuel Gravitonic movement;
- finite-fuel Tow where Tow-phase fuel state is unavailable;
- finite-fuel Intercept where Intercept-phase fuel state is unavailable;
- Tow contests/chains/cycles and separately scoped special interactions.

Missing movement-mass or engine facts remain UNKNOWN. Missing values are never treated as zero.

`unsupported_partial_waypoint` remains in the production enum/classifier only for compatibility with rows produced by older code. The supported normal-speed Move Most path no longer emits it.

## Product consequence

The previously documented true-partial normal-speed Move Most `implementation_gap` is now closed in production.

Turn Review should now emit a deterministic endpoint for that supported subset when the required owner-visible movement mass and engine facts are available. The change does not alter the general provenance rule: a deterministic prediction remains derived and `host_final: false`, not a factual observation.

## Next priorities

The next production-facing step is the already-pending Tow draft browser acceptance:

- save an explicit Tow target;
- verify drafted-target precedence over factual `mission1target`;
- verify `PREDICTED TOW` / `PREDICTED TOWED` rendering;
- verify switching away from Tow clears the local Tow target;
- verify Tow + Intercept remains rejected.

After that acceptance, inspect real Turn Review blocker populations before choosing the next mechanics transfer. Do not infer that zero-fuel, Gravitonic shortage, Tow phase-state, Intercept phase-state or special Host-order cases are solved merely because true-partial Move Most is now integrated.
