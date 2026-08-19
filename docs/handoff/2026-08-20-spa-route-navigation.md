# SPA route/navigation checkpoint — 2026-08-20

This checkpoint follows runtime feedback that the same game exposed different top-right controls on Starmap, page Dashboard and Intelligence, that dashboard/intel sub-tabs were lost on reload, and that the shared two-observer game chooser should not encode the selected observer in its home URL.

## URL model

The game chooser is canonical at:

- `/intelboard`

Legacy chooser URLs such as `/intelboard/georgul` are still accepted long enough to recover the remembered observer, then replaced with `/intelboard` without a reload. Selecting another observer column on the shared chooser no longer changes the URL.

Game URLs remain observer-aware because the same game can have different linked-observer/private-intel provenance:

- `/intelboard/<observer>/<gameId>`

Game surface and tab state is represented by query parameters:

- `/intelboard/<observer>/<gameId>?view=starmap`
- `/intelboard/<observer>/<gameId>?view=dashboard&tab=dashboard`
- `/intelboard/<observer>/<gameId>?view=dashboard&tab=turn-timing`
- `/intelboard/<observer>/<gameId>?view=intel&tab=combat`
- `/intelboard/<observer>/<gameId>?view=intel&tab=reports`
- `/intelboard/<observer>/<gameId>?view=intel&tab=communications`

`&` is only the standard separator between query parameters. Navigation uses the browser History API (`pushState`/`replaceState`) and React state, so changing surfaces/tabs does not reload the page.

Legacy `?intel=combat|reports|host|communications` is still read. The next route write canonicalizes it to `view=intel&tab=...`.

## Navigation controls

Starmap, page Dashboard and Intelligence now use the same game-surface control set and order:

1. Games
2. Dashboard
3. Intel
4. Starmap
5. Turn indicator

The active surface button is disabled/highlighted rather than disappearing. The page-Dashboard control row is placed below the global UTC/local clock strip to avoid the previous overlap.

The map VCR review popup remains a modal interaction, not a durable page/tab route. Closing it returns to the underlying surface.

## Dashboard tab persistence

All page-Dashboard tabs use the SPA route state, including:

- Dashboard
- VCR
- Battle Planner
- Reports
- Planets
- Starships
- Starbases
- Scoreboard
- Military intel
- Turn timing
- Diplomacy
- Time machine
- Advantages
- Settings

Internal cards/launchers also call the same route transition. Browser Back/Forward is subscribed through `popstate` and restores both the game surface and dashboard/intel tab.

## Scope / invariants

This batch is frontend routing/navigation only. It does not modify factual observations, private-intel access, provenance, background refresh, inference, combat simulation, VCR engine trace or RNG.

## Runtime acceptance checks

1. Open `/intelboard/georgul` (legacy) and confirm URL becomes `/intelboard` without changing the selected/remembered column.
2. Switch observer columns on the chooser; URL must remain `/intelboard`.
3. Open a game; no `view` parameter should default to Starmap.
4. Confirm the same top-right control set/order appears on Starmap, page Dashboard and Intelligence.
5. Click Dashboard -> Turn timing. URL should become `?view=dashboard&tab=turn-timing` without a document reload.
6. Refresh that URL. It must reopen page Dashboard on Turn timing.
7. Change to Scoreboard, VCR and Battle Planner; each tab must update `tab=` without a page reload.
8. Open Intel -> Reports. URL should become `?view=intel&tab=reports`; refresh must reopen Reports.
9. Switch Intel Combat/Reports/Communications and confirm URL and content stay synchronized.
10. Click Starmap. URL should become `?view=starmap`; refresh must reopen the map.
11. Use browser Back/Forward across several of the transitions above. Surface/tab should follow history without a full reload.
12. Open a map VCR marker. The modal replay should work as before; modal selection itself is intentionally not persisted as the page route.
13. Recheck global UTC/local clocks and top-right controls for overlap at the normal desktop width.

This checkpoint is source-reviewed only until the production frontend build and runtime checks above pass.
