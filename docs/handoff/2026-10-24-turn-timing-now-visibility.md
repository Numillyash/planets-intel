# IntelBoard Turn timing — explicit current-time marker (2026-10-24)

## Context and root cause

On the operational Dashboard > Turn timing for Kojak City Sector (example T15),
the yellow dashed vertical line in every per-player smoothed-density plot appeared
unlabelled and was mistaken for an average of player activity.

The source in `frontend/src/features/map/PlayerActivityPanel.tsx` already
calculated the line from `new Date().getHours()/getMinutes()/getSeconds()`.
This was **already an actual current-local-time marker**, not a mean/median.

## Change (PR #67)

- Each SVG has a visible `NOW` label next to the dashed yellow line.
- Above the player cards, one live legend shows the current browser-local
  time and the corresponding UTC time, including browser time-zone context.
- A single parent clock updates each chart every 30 seconds and cleans up
  its interval; individual charts no longer mount their own timers.
- All the charts use the exact same `Date` on each render, so the line cannot
  disagree between players or open/ready plots.
- The marker includes a tooltip and accessible SVG description clarifying that
  it is **not** an average, and the panel explanation covers it explicitly.
- Activity KDE smoothing, UTC-to-local sample conversion, raw sample ticks,
  server data, polling and after-host median values remain unchanged.
- Chrom(e/ium) regression fixture is served by Vite **dev only** at
  `/test/turn-timing-marker.html`. Test freezes browser time at
  2026-10-24T13:41:00Z in `Europe/Moscow`; checks four chart positions,
  header LOCAL=16:41 and UTC=13:41, advancement to 16:43, and mobile view.
  Screenshots are uploaded by the Public surface browser smoke workflow.
- Workflow Chromium runner is pinned to `ubuntu-24.04` because the Playwright
  1.56 runner is unsupported on GitHub's Ubuntu 26.04 `ubuntu-latest`.

## Release/deployment

Do not assert production installed until the operator runs the CentOS
deployment script and reports `DEPLOY OK`. After PR and main/operational-ui
CI both succeed and deployment branch fast-forwards, deploy:

```bash
bash /opt/planets-intel/scripts/deploy/production.sh
```

Check Dashboard > Turn timing in an **owned** sector: NOW/LOCAL/UTC visible,
aligned vertical line, movement after time passes, no regression in curve
shape or median labels.

If resuming in a fresh chat, verify live GitHub HEAD / PR #67 / GitHub Actions
rather than treating SHA values here as persistent live state.
