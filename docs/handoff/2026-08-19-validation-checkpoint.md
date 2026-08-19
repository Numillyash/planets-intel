# Operational UI validation checkpoint — 2026-08-19

This checkpoint intentionally stops new feature work and freezes the current code for runtime validation.

## Code checkpoint

- Working branch: `feature/operational-ui`
- Code HEAD deployed by the operator before this document-only checkpoint: `8845dc3fef71831af48ec6de573e414dc7f4aa09`
- Commit subject: `test: guard authoritative battle runtime builder`
- Compared with `checkpoint/2026-08-19-operational-ui-handoff` (`7772544`), the code checkpoint is 34 commits ahead.
- The server successfully fast-forwarded from `024f182` to `8845dc3`.
- Production backend image build completed successfully, including frontend `npm run build` and backend `compileall`.
- `docker compose up -d` recreated/started the backend and reported postgres healthy.

## Immediate runtime observation after deploy

The first health probe was executed almost immediately after the backend container started and returned:

```text
curl: (56) Recv failure: Connection reset by peer
```

`docker compose logs --tail=100 backend` returned no lines at that instant. This is NOT sufficient evidence of an application failure because the probe occurred less than a second after container start. Before debugging code, wait a few seconds and re-check container state, health, and logs.

Recommended first check:

```bash
cd /opt/planets-intel
sleep 5

docker compose ps
curl -v http://127.0.0.1:18080/api/health
printf '\n===== LOGS =====\n'
docker compose logs --tail=200 backend
```

If the backend is restarting/exited, inspect the logs before making any further code changes.

## What is in the current validation candidate

### Game chooser / turn rail

- Turn-state merge between `games/list.turnstatus` and same-turn `loadinfo.players` no longer gives unconditional precedence to the compact marker.
- READY / VIEWED / unopened are reconciled monotonically within the same turn.
- Explicit inactive/dead and computer markers remain structural states and are not resurrected by stale progress metadata.
- A true `unknown` state exists instead of silently converting missing turn facts to unopened.
- Loadinfo data is used for turn-state reconciliation only when its game turn equals the game-list turn.
- Rail density handling covers larger games, including 20+ slots.
- Joining/Finished games do not present the Running-only turn rail as current-turn operational state.
- Observer selection remains route/remembered-observer aware.
- Account profile images fall back to initials if the optional image lookup or browser image load fails.
- Cached known games remain visible when the live `games/list` lookup fails; the UI warns about degraded live metadata instead of hiding the cached list.

### Fight-or-Fail / missed-turn indication

- Live public `turnsmissed` is exposed as `turns_missed` when Planets.nu actually supplies it.
- Missing or invalid values remain unknown; known zero remains zero.
- Current-turn player cells can show yellow/orange/red missed-turn outlines based on factual `turnsmissed`.
- No historical/cached missed-turn value is promoted to a current fact.
- The UI does not claim a FoF/drop-risk state when `turnsmissed` is unknown.

Important: exact host-specific removal thresholds still require runtime confirmation against real Planets.nu data/settings before being treated as a fully validated Fight-or-Fail predictor.

### Public/cache correctness

- Cached game-list membership requires current canonical player identity instead of returning stale membership from old status alone.
- Canonical game-detail fallback only uses current-turn score/activity observations.
- Historical READY / score data is not promoted into the current turn.
- Missing compact all-player turn rail and missing missed-turn streak stay unknown in cache fallback.

### Background private refresh

- Running and Joining games are candidates for browser-independent private refresh.
- Membership matching uses a positive external account id and a canonical username fallback.
- NULL/sentinel account ids are prevented from matching unrelated NULL slots.
- Equivalent `(game, accessible observer set)` refresh jobs are deduplicated.
- One account/private-sync failure is isolated to that observer result rather than aborting the whole observer set.
- Diagnostic command added: `python -m app.scripts.inspect_background_refresh` inside the backend runtime.

### Turn-state diagnostic

`inspect_account_games` can compare the raw compact `games/list` rail with the raw `loadinfo` rail/player fields for a chosen game. This is the primary diagnostic for the reproduced Estes/Lizard VIEWED discrepancy.

Example after deployment:

```bash
docker compose exec -T backend \
  python -m app.scripts.inspect_account_games <LINKED_ACCOUNT_ID> --game-id 682932
```

The diagnostic prints both source turns, both compact rails when present, and relevant per-player fields including turn/miss/drop/status/ready tokens.

### VCR / deterministic combat

- Added fighter-trace safety regression coverage for launches, fighter attacks, dogfight losses and beam-vs-fighter events.
- Visual tracing remains presentation-only and must not make extra RNG calls.
- Added `inspect_vcr_trace.py` diagnostic to compare a real stored VCR visual trace with the deterministic terminal replay result.
- Added a guard test ensuring the Battle Simulator runtime facade installs the authoritative payload builder rather than accidentally using the stale duplicate implementation path.

## Runtime validation still required before calling this done

1. Re-check backend health after startup delay. Do not diagnose the immediate connection reset until this is done.
2. Open the game chooser and validate the Estes `#682932` slot 2 Lizard case against Planets.nu at the same moment.
3. Validate READY / VIEWED / unopened colors, dead players, computer players and 20+ slot layout in real games.
4. Validate profile artwork on real linked accounts and initials fallback.
5. Validate Joining and Finished rows/semantics.
6. Inspect real `turnsmissed` values and compare warning outlines with Planets.nu/Fight-or-Fail behavior. Do not hard-code additional host assumptions without evidence.
7. Leave the browser closed for at least one scheduler interval and inspect background refresh logs/diagnostic output.
8. Specifically validate Chanda membership fallback, shared observer-set dedup, Joining refresh and failure isolation.
9. Validate Battle Simulator VCR-only ships (including the previously important Rush case), current-known ships, race/advantage controls and right-side balance modes.
10. Run the real VCR trace diagnostic on representative carrier/torpedo fights and compare terminal result with the deterministic nonvisual engine.
11. Re-test hull #94 artwork in the deployed frontend.
12. Run the full backend unit test suite on the deployed checkout; the production image build itself does not execute unit tests.

## Invariants for the next work session

- known zero != unknown
- fact != inference != simulation
- current fact != historical fact
- combat-time fact != current fact
- missing data != zero
- unknown Host behavior = fail-closed
- visual VCR tracing must not change RNG progression or terminal result

## Resume rule

Do not start another broad implementation pass from chat history. Use GitHub as source of truth, read this file plus `docs/architecture/NEW_CHAT_START.md`, `docs/architecture/PROJECT_STATE.md`, `docs/architecture/CURRENT_HANDOFF.md` and `docs/handoff/2026-08-19-operational-ui-chat-handoff.md`, then begin from runtime validation results.

If validation finds a regression, make the smallest isolated fix with a regression test. If validation passes, continue with the remaining runtime-verification items above before new features.
