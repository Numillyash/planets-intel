# VCR bays/header + cross-game timing checkpoint — 2026-08-19

## Runtime feedback addressed

This batch follows the runtime validation of the previous VCR visual-polish deployment.

1. Fighter bays no longer all light together. Only one presentation pip is active on a factual `fighter_launch` frame, and successive launch events advance through the displayed bays sequentially.
   - The active physical bay is **not** a Host fact; NuHost Classic exposes bay count + launch event, not a physical bay identifier.
   - The sequential pip is explicitly presentation-only.
2. The VCR dashboard heading is contained inside its player shell with padding, min-width guards, overflow handling, and ellipsis/wrapping so the top-left title cannot spill into adjacent UI.
3. Added console-only `app.scripts.compare_player_timing_across_games`.
   - groups the same canonical username across different games;
   - compares per-turn Ready time distributions using Planets.nu `turnreadydate` when available;
   - also reports polling-bound first-Open distributions separately;
   - uses 24-bin hourly histogram intersection (100% identical distribution, 0% disjoint hours), preserving multimodal morning/evening behavior instead of collapsing it into one average.
4. Destruction presentation is now transient and dismissible.
   - ship artwork still fades/removes after factual destruction;
   - explosion and destroyed text can be clicked to dismiss immediately;
   - after their CSS animation they become `visibility:hidden`, so an invisible overlay cannot continue intercepting UI;
   - the normal ship label is removed once the transient destruction presentation is no longer active.

## Files changed since previous checkpoint `2c865d7`

- `frontend/src/features/dashboard/CombatReplayPlayer.tsx`
- `frontend/src/features/dashboard/vcr-hull-artwork.css`
- `backend/app/scripts/compare_player_timing_across_games.py`
- `backend/tests/test_compare_player_timing_across_games.py`

## Cross-game timing diagnostic

After deploying the image, run all repeated usernames in MSK time:

```bash
cd /opt/planets-intel
docker compose exec -T backend \
  python -m app.scripts.compare_player_timing_across_games \
  --utc-offset +03:00 \
  --min-ready-samples 2
```

Or a specific username:

```bash
docker compose exec -T backend \
  python -m app.scripts.compare_player_timing_across_games \
  --username "helping die" \
  --utc-offset +03:00 \
  --min-ready-samples 2
```

Interpretation:

- `READY overlap` is the primary comparison because it uses exact `turnreadydate` samples when present.
- `OPEN overlap` is secondary because first-open is bounded by the polling interval.
- Overlap compares whole hourly distributions, so a bimodal morning/evening habit remains bimodal.

## Required deploy/runtime validation

1. production frontend build (`tsc --noEmit && vite build` through Docker build),
2. full backend unittest suite,
3. `/api/health`,
4. Chanda T18 VCR #40:
   - only one fighter-bay pip flashes per launch,
   - successive launches advance the active pip,
   - VCR title stays inside header,
   - destroyed Rush artwork disappears,
   - explosion/text disappear automatically and immediately when clicked,
   - no invisible destruction element blocks subsequent UI interaction,
5. run the cross-game timing diagnostic and save its console output for analysis.
