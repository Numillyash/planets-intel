# Starmap VCR review checkpoint — 2026-08-20

## Runtime baseline

The deployed baseline before this batch is:

`609eeeca84bc6798cea901003cf82f9d04708509`

User runtime verification for that baseline reported:

- production backend image build succeeded, including frontend `npm run build` and Python compileall;
- full backend unittest suite: `Ran 159 tests ... OK`;
- backend and PostgreSQL containers were up;
- `/api/health` returned `{"status":"ok","service":"planets-intel-backend"}`.

## User runtime findings after that deploy

1. Global/local clock cards were visually overlapped by the fixed `Starmap` action while the page dashboard was open.
2. Starmap still showed large explosion/VCR-looking markers and labels. Desired behavior is the original-style review flow: click a VCR on the starmap, open a subwindow where all turn VCRs can be browsed, and remove each reviewed VCR marker from the map.
3. `This game / All current games` turn-timing scope was confirmed correct and must not regress.

## Implemented in this batch

### Clock layout

- The shared global/local clock strip now centers its clock cards in its own row instead of anchoring them at the same top-right edge used by fixed operational actions.
- The `Starmap` return button remains in its original action lane; it is not moved down into dashboard header content.
- Turn-timing code and cross-game aggregation were not changed.

### Actual VCR review subwindow from starmap

- Starmap VCR selection now opens a dedicated modal review subwindow over the starmap rather than routing the click through the old static combat evidence panel.
- The subwindow uses the existing deterministic `VcrDashboardPanel` / `CombatReplayPlayer` implementation.
- The selected map VCR is opened directly by `vcr_id`.
- The subwindow exposes the existing complete turn VCR list and `Previous` / `Next` controls.
- Escape, Close, or clicking the modal backdrop returns to the map.
- The full `Intel -> Combat` surface remains available separately.

### Reviewed marker lifecycle

- Reviewed VCR state is local presentation state, not intelligence evidence and not a database fact.
- State is keyed by `game + turn + vcr_id` and stored in browser local storage so reviewed markers stay hidden after a page refresh during the same turn/game context.
- Selecting a VCR in the review window marks it reviewed. This includes navigation with Previous/Next.
- Active Pixi VCR graphics are hidden immediately when the review event is emitted.
- Subsequent starmap redraws consult the stored reviewed state and do not recreate reviewed current-turn VCR contacts.
- No combat engine, replay RNG, VCR source payload, observation fact, or inference is mutated by this behavior.

### Explosion/VCR duplicate rendering

- A long-range `ship_explosion_detected` HostEvent and a factual VCR remain separate evidence in storage and in the Reports UI.
- On the starmap only, when a current-turn factual VCR exists at the same coordinate, the VCR owns the actionable marker and the duplicate large HostEvent explosion marker/label is suppressed.
- Report-only explosions with no factual current-turn VCR at that coordinate are still rendered as explosion reports.

## Files changed from deployed baseline

- `frontend/src/components/dual-clock.css`
- `frontend/src/features/dashboard/VcrDashboardPanel.tsx`
- `frontend/src/features/map/CombatEventPanel.tsx`
- `frontend/src/features/map/currentCombatMapRegistry.ts`
- `frontend/src/features/map/historicalTrackScene.ts`
- `frontend/src/features/map/hostEventScene.ts`
- `frontend/src/features/map/operational-dashboard-bridge.css`
- `frontend/src/lib/vcrReviewState.ts`

## Runtime acceptance checks

Before calling this batch deployed/validated:

1. production image build must pass (`tsc --noEmit`, Vite build, Python compileall);
2. full backend unittest suite must still pass;
3. deploy and verify `/api/health`;
4. hard-refresh the browser;
5. open the full page dashboard and verify GLOBAL/LOCAL clocks no longer overlap `Starmap`;
6. return to the starmap and verify factual VCR positions no longer also carry the large duplicate `Explosion · <ship>` HostEvent label;
7. click an unread VCR map marker and verify a modal VCR review window opens over the map at that exact VCR;
8. use Next/Previous and verify each selected VCR marker disappears from the map behind the modal;
9. close the modal and verify reviewed VCR markers stay absent while unread VCR markers remain;
10. hard-refresh and verify reviewed VCR markers for that game/turn remain hidden;
11. verify a report-only long-range explosion with no VCR remains visible on the map and still opens Reports;
12. verify Dashboard -> Turn timing still switches correctly between `All current games` and `This game`.

## Semantics

`reviewed` is a local UI acknowledgement only. It must never be presented as evidence that a combat result, ship identity, post-combat state, or Host behavior has been independently confirmed.
