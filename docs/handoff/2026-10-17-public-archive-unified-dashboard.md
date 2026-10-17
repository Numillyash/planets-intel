# Unified public archive Dashboard — 2026-10-17

## Scope

PR #57 changes `/intelboard/public/<gameId>` from a standalone affinity-only
page into a read-only use of the existing GameDashboard tab shell.

- All public sectors can use the shared Dashboard, public settings, roster,
  Commander Intelligence and any existing public score cache.
- Finished public sectors (`status=3`, `isprivate=false`) can request
  a specific `playerid` and `turn` with `/game/loadturn`.
- An archival RST is normalized into a separate `public_finished_archive`
  read model; it is **never** written to private observation batches, tied
  to linked accounts, or consumed by private order/planning endpoints.
- Existing Pixi map scene/geometry rendering is shared. A read-only archive
  canvas does not invoke private observer/history, draft or shared-intel APIs.
- The returned RST's `rst.game.id`, `rst.game.turn`, and `rst.player.id`
  must match the requested finished public sector, turn and player slot.
- A historical player slot is a perspective, not proof of which account held
  that slot at the time, especially after replacements.
- Snapshot facts come from selected slot's archived visibility, **not** an
  omniscient composite across other players. Current public game metadata
  is never implicitly relabelled as historical settings.

## Actual upstream contract evidence

On 2026-10-17, a temporary CI smoke test using the same Python
`fetch_finished_public_turn` adapter successfully requested **public finished**
game #184630, slot 4, turn 17, with no API key. Source check confirmed
the game was finished and public; returned identifiers matched the request.
Only field counts were logged: 500 planets, 16 ships, 1 starbase.
Evidence:
https://github.com/Numillyash/planets-intel/actions/runs/39058883241

The temporary CI workflow was deleted after it produced the evidence.
A non-logging maintenance probe lives at
`backend/app/scripts/probe_public_archive.py`.

## Boundaries and follow-up

This slice does not guarantee every old game's RST availability; Planets.nu
may reject a turn or return incomplete/unsupported data. The API fails closed.
It does not backfill `loadall` or expand private grants. There is no
automatic ingestion of an entire foreign sector.

The current public scoreboard uses existing local score history if available.
Dedicated cached public `loadscores`, archival event/VCR timeline integration,
full unified operation panels, and browser-screenshot visual acceptance are
follow-up work. Private-only tabs remain unmounted in public mode.

Do not call this deploy-verified until the host operator runs
`scripts/deploy/production.sh` and checks its final SHA/health.
