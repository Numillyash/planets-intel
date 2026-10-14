# VCR fighter renderer validation fix — 2026-08-19

## Runtime symptom

During validation of the deployed `8845dc3` candidate, historical VCR playback showed factual/simulated fighter state in the status cards (`fighters_out` > 0) and emitted fighter launch events, but no individual fighters were visible on the battlefield.

Representative live case:

- game: Chanda M Sector (`682909`)
- turn: `18`
- VCR: `40`
- combat: Gorbie Class Battlecarrier vs Rush Class Heavy Carrier
- observed frame: left `OUT 18`, right `OUT 10`

## Root cause

The frontend had two independent VCR battlefield renderers.

- `CombatReplayPlayer.tsx` was the newer renderer and already consumed `fighter_tracks` plus fighter/beam/dogfight trace effects.
- `VcrDashboardPanel.tsx` still contained an older duplicated Battlefield implementation that rendered ships and torpedoes only.

The live VCR tab used the old `VcrDashboardPanel` renderer, so the backend trace could contain fighter state while the DOM never created fighter elements.

## Fix

Commit `3e5e2d7ae00b7f99c5eb6e3d0555c4ceb0f1e848` (`fix: use shared fighter-aware VCR renderer`) removes the duplicate VCR dashboard playback implementation and delegates actual playback to the shared `CombatReplayPlayer`.

This also prevents the historical VCR tab and Battle Simulator replay from silently diverging again in supported visual effects.

## Required validation after deploy

1. Rebuild/redeploy the frontend/backend image from the current `feature/operational-ui` head.
2. Re-open game `682909`, turn `18`, VCR `40`.
3. Verify that individual blue/orange fighter markers are visible while `fighters_out > 0`.
4. Verify fighters move toward/away from the opposing ship according to trace tracks.
5. Verify fighter attacks, dogfight loss flashes and beam-vs-fighter effects are visible in representative frames.
6. Verify Previous/Next VCR navigation still works and switching VCRs resets playback correctly.
7. Verify terminal battle result is unchanged; visual presentation must not alter deterministic replay state/RNG.

If `fighters_out > 0` is still visible but no fighter markers appear after this exact fix is deployed, do not synthesize positions from counts. Inspect the live replay JSON / `inspect_vcr_trace` output and confirm that same-frame `fighter_tracks` are present; missing tracks are then a backend/transport issue, not a renderer issue.
