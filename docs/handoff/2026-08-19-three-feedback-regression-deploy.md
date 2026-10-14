# Three-feedback regression deploy checkpoint — 2026-08-19

This checkpoint closes the three user feedback groups immediately preceding deployment validation.

## Code head before this docs-only checkpoint

`49bc866e45e3bddf2c824eead78697a87c408b37`

## 1. Visual VCR feedback

Verified in source:

- `VcrDashboardPanel` uses the shared `CombatReplayPlayer`; the old fighter-blind renderer is no longer the dashboard path.
- Individual fighter tracks are rendered.
- Fighter lanes span 10%..90% of the battlefield across 19 deterministic presentation lanes.
- Large hull artwork is contained in a fixed artwork shell with labels laid out as separate flex children below it; the artwork is reduced relative to the original oversized version.
- `fighter_attack` draws a source-fighter -> target-ship laser.
- `fighter_dogfight_loss` draws a fighter -> fighter presentation shot plus a loss flash.
- `beam_ship` draws source ship -> target ship.
- `beam_fighter` draws source ship -> actual killed fighter id/x from the trace.
- Trace hooks delegate to the authoritative engine and make no additional RNG calls.
- Playback no longer skips trace frames at 1x/2x/4x. Speed changes timer cadence while every frame is visited (`e3d5bb7`). This prevents one-frame weapon events from disappearing visually.

Runtime validation still required after deploy: Chanda T18 / VCR #40 Gorbie vs Rush, especially fighter lasers, dogfight shots, ship-to-fighter beams and label clearance.

## 2. VCR Battle Planner feedback

Verified in source:

- Repeated 10,000-battle sampling returns the requested battle count and samples deterministic Classic seed results with replacement.
- Mean terminal statistics are reported per side: shield, damage, crew, torpedoes and fighters.
- UI presents survival, average shield/damage/crew, average torps left, average torps fired, average fighters left and average fighters lost.
- Torps fired is explicitly start minus terminal torpedoes.
- Fighters lost is explicitly start minus terminal fighters after the deterministic engine returns surviving launched fighters.
- A regression test now guards the mean terminal statistics (`49bc866`).
- Factual deterministic baseline and source-seed scenario use the same Battle Simulator-style stat cards instead of the old cramped summary layout.
- The VCR planner side cards have exactly two ammo columns (fighters + torpedoes); the accidental empty third column is removed without changing the standalone simulator's real three-modifier grid (`544f708`).

Runtime validation still required after deploy: VCR #40 -> run 10,000 battles and inspect both layout and values.

## 3. Scoreboard / turn timing feedback

Verified in source:

- Scoreboard is reduced to `PlayersTable` + `MilitaryScoreChart`.
- Military attribution and VCR fighter evidence moved to the separate `Military intel` tab.
- Player timing moved to the separate `Turn timing` tab.
- Backend exposes per-turn `open_utc_minutes` and `ready_utc_minutes` instead of forcing the UI to use one circular average.
- The old circular centers remain only for API compatibility.
- Turn timing renders two 24-hour histograms per player: first observed open and exact/available Planets.nu `turnreadydate` ready samples.
- Browser local timezone conversion is applied before hour binning.
- Bimodal habits (for example morning + evening) therefore remain two visible peaks.
- Median delay after host is shown separately and is not presented as time-of-day.
- A regression test guards preservation of separate time-of-day samples.

Runtime validation still required after deploy: inspect one player with multiple historical samples and verify the histogram against known activity where possible.

## Verification boundary

The code-level regression review is complete for these three feedback groups. GitHub push status is not treated as evidence that CI passed: the connector did not expose a completed push run for this head.

Before replacing the running service, the server should:

1. fast-forward `feature/operational-ui`;
2. build the production backend image (this runs frontend `npm run build` and Python `compileall` in the Dockerfile);
3. run the full backend test suite with `backend/tests` mounted into `/app/tests` because the production image intentionally does not copy tests;
4. only then run `docker compose up -d`;
5. verify `/api/health` and backend logs;
6. perform the three runtime browser checks above.

No database migration is introduced by this feedback package.
