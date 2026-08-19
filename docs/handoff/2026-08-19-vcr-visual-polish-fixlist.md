# VCR visual polish fixlist — 2026-08-19

Baseline deployed before this batch:

- branch: `feature/operational-ui`
- deployed checkpoint: `475414c5847e5890d3259f549c7fba41bfb69d05`
- production image build: passed
- backend tests: `Ran 148 tests ... OK`
- `/api/health`: OK

This batch is driven by live browser validation after that deploy.

## User-visible regressions / missing presentation

1. Long VCR object labels can collide with the scene edge / object artwork.
2. The opening approach appears frozen because the presentation edge clamp holds objects in place for the first combat cycles. Object movement must be visible from cycle 1 without changing engine coordinates.
3. Ship artwork is vertically offset above the combat axis because the whole artwork+label column is centered on the axis. The artwork itself must be centered on the combat axis; labels must be positioned independently below it.
4. Weapon readiness is under-exposed. Exact beam and launcher slot charge states already exist in the deterministic trace and must be shown per slot. Classic fighter bays do not have a continuous recharge counter in this engine; show factual bay count / launch activity instead of fabricating a charge percentage.
5. Shield and hull condition should be read primarily as bars with numeric values as secondary detail. Hull integrity must use the factual combat `damage_limit` so Lizard >100% damage remains correct.
6. A destroyed object currently remains visible with no destruction feedback. Add presentation-only explosion/fade; never alter the deterministic trace/result.
7. Torpedo projectiles currently fly on a central straight lane. The trace already records factual `hit`; presentation should make misses visibly pass the target and hits converge on it, using deterministic presentation lanes and no additional combat RNG.
8. Turn Timing lost useful compact summary values when it was converted to histograms. Keep multimodal histograms as primary representation, but restore the existing circular-center `typical_open_utc_minute` / `typical_ready_utc_minute` as secondary summaries and keep sample counts / median-after-host values visible.

## Acceptance checks

- Chanda M Sector T18 VCR #40: Gorbie/Rush artwork centered on combat axis; labels do not overlap artwork or edge.
- Ship approach moves visibly from the first playback frames.
- Carrier combat: individual fighters remain spread vertically; fighter/beam shots terminate on rendered targets.
- Per-slot Beam and Torpedo launcher readiness is visible and follows trace slot values.
- Fighter bays are represented without invented recharge semantics; launch activity can pulse when a factual `fighter_launch` event occurs.
- Shield and Hull bars change through combat and survive Lizard damage-limit semantics.
- Destroyed Rush produces an explosion/fade and artwork disappears while terminal result remains unchanged.
- Torpedo misses visibly pass above/below the target; hits converge on the target center. No RNG calls are added for presentation.
- Turn Timing keeps 24-hour histograms and again shows compact typical open/ready times.

## Invariants

- Presentation changes must not add combat RNG calls.
- Factual VCR payloads are immutable.
- Visual state may be derived from exact trace fields, but must not be persisted as current intel.
- Unknown Host behavior remains fail-closed.
