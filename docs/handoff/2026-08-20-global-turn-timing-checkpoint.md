# Global turn timing redesign checkpoint — 2026-08-20

## Baseline

Runtime-validated baseline before this batch:

`fd35550c9e485f1d0f3a449f86e8aee6ac285f0f`

The server build for that checkpoint passed and the full suite reported `Ran 155 tests ... OK`; `/api/health` was OK. The subsequent backend-only diagnostic cleanup ended at `9f4f98401a8e63492f915eb5facdd0d8a192588d`.

## Requested redesign

1. Replace coarse hourly bars with a smooth time-of-day graph so morning/evening modes remain visually obvious without inventing a single average window.
2. Show global and local time at the top of IntelBoard and make the intelligence chart's time scale unambiguous.
3. Do not introduce a three-hour prediction window; the distribution itself is the primary representation.
4. Combine the same opponent's timing observations across current games, ideally all current games accessible to the user.

## Implemented

### Smooth timing curves

- `Turn timing` now renders a circular Gaussian-smoothed density curve over the factual per-turn minute samples.
- The smoothing is presentation-only; raw factual observations remain visible as ticks below the curve.
- Curves are normalized per chart and explicitly described as habit shape, not absolute probability.
- Separate Ready and First-observed-open curves remain.
- No three-hour prediction window or threshold was added.

### Dual time reference

- A shared top strip is shown on every authenticated IntelBoard surface (picker, game dashboard, Accounts).
- It displays `GLOBAL · UTC` and the browser's `LOCAL` timezone/time plus current UTC offset.
- Timing charts use local time as the bottom axis and an aligned UTC reference as the top axis.
- A current-time marker is shown in the timing chart.

### Cross-game aggregation

- The activity API still returns selected-game factual samples and now also returns combined samples for the same canonical username across current games.
- `All current games` is the default UI scope; `This game` remains available as a toggle.
- Current-game state remains current-game state and is not merged across games.
- Combined data are user-scoped: only Running/Joining games reachable through the authenticated user's active linked Planets.nu observers are considered.
- Canonical usernames are case/whitespace normalized.
- Human slots only are aggregated.
- activity-state placeholders are rejected as identities.
- if the same canonical username maps to multiple human slots in one game, that game's identity is treated as ambiguous and excluded from the aggregate.
- The API reports per-player aggregate game count/sample counts and total current games considered.

## Files changed since `9f4f984`

- `backend/app/api/routes/historical_intel.py`
- `backend/app/services/player_activity.py`
- `backend/tests/test_player_activity_state.py`
- `frontend/src/components/DualClock.tsx`
- `frontend/src/components/dual-clock.css`
- `frontend/src/features/map/PlayerActivityPanel.tsx`
- `frontend/src/features/map/player-activity.css`
- `frontend/src/main.tsx`
- `frontend/src/types/activity.ts`

## Regression guards

Backend tests now explicitly cover:

- canonical cross-game username normalization;
- state-placeholder rejection;
- exclusion of computer slots;
- exclusion of ambiguous duplicate same-game identities;
- preservation of the existing turn-state monotonicity and raw minute-sample behavior.

## Required deploy validation

This checkpoint has source-level review only. Before calling it runtime-valid:

1. production image build must pass (`npm run build` + Python compileall),
2. full backend unittest suite must pass,
3. deploy and verify `/api/health`,
4. hard-refresh browser,
5. verify the top UTC/local clocks on both picker and game dashboard,
6. open `Turn timing` and verify smooth Ready/Open curves, factual sample ticks, UTC/local axes and current-time marker,
7. toggle `All current games` / `This game` for a repeated player such as `haco_fried`, `rodrox`, `helping die`, or `georgul` and verify sample/game counts visibly change in the expected direction.

## Important semantics

- Ready uses factual Planets.nu `turnreadydate` where available.
- Open remains polling-bound.
- Cross-game aggregation is descriptive evidence only. It does not convert activity history into a claim about continuous online presence or a guaranteed future action time.
