# VCR visual polish deploy checkpoint — 2026-08-19

## Baseline

Last runtime-validated/deployed server checkpoint before this batch:

`475414c5847e5890d3259f549c7fba41bfb69d05`

That deployment passed production frontend/backend image build, the full 148-test backend suite, health check, and backend startup.

## Code head before this docs-only checkpoint

`d1ee000cf5a4b69560348bf59b2f48e9790afbcd`

## Closed feedback items

1. VCR artwork and labels are now separate layers. Artwork is centered on the combat axis; labels sit independently below it with bounded width/ellipsis.
2. Opening movement no longer disappears into an edge clamp. The factual 30..610 combat coordinate space maps onto a stable 10%..90% presentation stage, so one engine-unit movement is visible from cycle one. Minimum close-combat spacing remains presentation-only.
3. Fighter and beam source/target geometry uses the same combat-axis anchor as artwork.
4. Exact beam and torpedo-launcher per-slot charge values are shown. Fighter bays deliberately do not show a fabricated percentage: Classic combat has a per-cycle launch roll, not a continuous bay charge counter. UI shows factual bay count and pulses on a factual fighter-launch event.
5. Shield and hull integrity are bar-first. Hull integrity uses exact trace `damage_limit`; Lizard 151-damage-limit semantics therefore remain representable.
6. Trace exposes a destruction transition and the renderer presents explosion + artwork fade/removal. This does not alter terminal combat state.
7. Torpedo effects use the factual engine-hook `hit` boolean. Hit trajectories converge on the target; misses deterministically pass above/below it. Lane/bend choice is presentation-only arithmetic and performs no combat RNG calls.
8. Turn Timing keeps multimodal 24-hour histograms and restores `Typical open` / `Typical ready` as secondary browser-local summaries, plus the existing median-after-host metrics.

## Regression guards added

- VCR trace still matches the non-tracing deterministic engine terminal result/cycle count.
- trace presentation fields include `damage_limit`, `destroyed`, `bay_count`, beam slots, launcher slots.
- destruction transition emits a side-specific destroyed event without changing deterministic result.
- torpedo presentation events expose factual boolean `hit` plus source/target combat coordinates, while terminal results remain identical.

## Files changed since deployed baseline

- `backend/app/services/vcr_replay_trace.py`
- `backend/tests/test_vcr_trace_fighter_safety.py`
- `backend/tests/test_vcr_trace_torpedo_presentation.py`
- `frontend/src/api/vcrReplay.ts`
- `frontend/src/features/dashboard/CombatReplayPlayer.tsx`
- `frontend/src/features/dashboard/vcr-hull-artwork.css`
- `frontend/src/features/map/PlayerActivityPanel.tsx`
- `frontend/src/features/map/player-activity.css`
- `docs/handoff/2026-08-19-vcr-visual-polish-fixlist.md`

## Required deploy gate

This checkpoint has source-level review only. Before deployment:

1. build the production backend image (which runs frontend `npm run build` and backend compileall),
2. run the full backend unittest suite from the server checkout,
3. deploy only if both pass,
4. verify `/api/health`,
5. hard-refresh browser and validate Chanda T18 VCR #40 plus one torpedo VCR and Turn Timing.

## Runtime validation targets

### Carrier VCR

- artwork visually centered on range line,
- no label/artwork collision,
- approach moves from first frames,
- fighter spread retained,
- fighter/beam shots terminate on rendered targets,
- beam slot readiness and fighter-bay state visible,
- destroyed Rush explodes and disappears.

### Torpedo VCR

- launcher slot readiness visible,
- hit projectile converges on ship,
- factual miss visibly passes above/below ship,
- no central-only projectile rail.

### Turn Timing

- histograms remain per-turn/multimodal,
- Typical open/ready secondary summaries are restored,
- median-after-host summaries remain present.
