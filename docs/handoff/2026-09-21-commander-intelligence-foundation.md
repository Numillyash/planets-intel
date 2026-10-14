# 2026-09-21 — Commander Intelligence foundation

Repository: `Numillyash/planets-intel`
Active branch: `feature/operational-ui`

This handoff records the first bounded vertical slice of Commander / Player
Intelligence. GitHub remains the source of truth; inspect the actual branch HEAD
before relying on any SHA in this document.

## Production checkpoint before this slice

The server was successfully deployed on 2026-09-21 at:

```text
d0aca955914db38abf6d49cac61a8df7e0de4b82
```

Observed deploy result:

```text
Build: OK
Backend tests: OK (306)
DB: 0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
Log: /opt/planets-intel/logs/deploy/20260921-122316-production.log
```

The Commander Intelligence slice adds migration
`0019_commander_intel_cache`, so it is not considered production-accepted
until that migration is deployed and the live dossier is checked.

## Product boundary

The implementation preserves:

```text
public factual observation
!= derived historical summary
!= analyst annotation
!= behavioral inference
!= prediction
```

No "ally", "rival", "coordination" or similar behavioral label is produced.

A shared game is not treated as proof that two usernames played at the same
time. Turn overlap is derived only from bounded participation intervals.

## Existing infrastructure reused

The slice reuses:

- `PlanetsNuClient` for official public Planets.nu requests;
- canonical `Game` / `GamePlayerSlot` for the current-game active roster;
- the existing FastAPI auth/router stack;
- the existing Game Dashboard rather than creating another application;
- existing race naming/UI infrastructure.

No second Time Machine or historical replay subsystem was added.

## Public transport caches

Two backend-side caches were added:

```text
public_player_history_cache
public_game_info_cache
```

They store the latest public API payload plus source/fetch provenance.

They are transport caches, not canonical relationship facts and not inference
tables.

The player-history adapter requests:

```text
/games/list?username=...&status=2,3
```

and also filters statuses 2/3 locally because Planets.nu username game-history
queries can ignore other search terms.

Historical shared-game detail uses:

```text
/game/loadinfo?gameid=...
```

Requests are backend-side and cached. Historical shared-game loadinfo fan-out is
bounded with a concurrency semaphore. Stale cached payloads are explicitly
identified when used as an upstream-failure fallback.

## Participation reconstruction

The read-time derivation preserves multiple participation periods for one
username in one game.

Strong evidence:

- public join event;
- public drop event;
- attributable slot/player id;
- event ids;
- turn values.

Fallback evidence:

- `players[].turnjoined`;
- `players[].status`;
- `players[].statusturn`;
- current observed game turn for an active roster row.

Intervals carry:

```text
username
game_id
slot_id
turn_from
turn_to
race_id / attributable race name
source
source_event_ids
reconstruction_quality
bounds_known
basis
```

One-sided event evidence remains one-sided. For example, a drop event with no
attributable join produces an unknown `turn_from`; it is not silently expanded
back to turn 1.

## Pairwise derived summary

For each pair of active human commanders in the current canonical roster the
service derives, from public running/finished history:

- shared games other than the current game;
- concrete per-game participation intervals;
- exact disjoint overlap intervals;
- exact overlap-turn totals when all interval bounds are known;
- bounded known-overlap lower bounds when reconstruction is partial;
- first/last shared occurrence only when all shared-game creation dates are
  attributable.

Unknown public history or unavailable loadinfo is represented as unknown/partial,
not as zero overlap.

## API

New authenticated endpoint:

```text
GET /api/games/{game_id}/commander-intelligence
```

Top-level provenance explicitly reports:

```text
analysis_kind = derived_historical_summary
method_version = commander_overlap_v1
behavioral_inference = false
facts_unchanged = true
```

## Minimal UI

A new live-roster Game Dashboard tab:

```text
Commander intel
```

provides:

- selected Commander / Player Dossier;
- public running/finished game history;
- current-game peers with other shared games;
- exact or lower-bound overlapping turn counts;
- drill-down to concrete game ids and participation/overlap intervals;
- bounded attributable race history with explicit coverage caveat;
- transport-cache/source provenance;
- an explicit evidence-boundary notice.

The tab is intentionally unavailable as a historical Time Machine snapshot:
the dossier is anchored to the current canonical roster plus public history.

## Tests

Backend regression coverage includes:

- username canonicalization;
- multiple join/drop participation periods;
- join+active-roster interval closure;
- drop-only unknown start;
- roster fallback;
- exact disjoint overlap without double-counting;
- unknown interval edges never creating false exact overlap;
- games/list requested-status filtering enforced locally.

CI is the merge gate for backend compilation/tests, frontend TypeScript/Vite
build and production-image build.

## Remaining Commander Intelligence work

The first slice is intentionally bounded.

Not yet implemented:

- complete race history for every public-history game; the first slice only
  attributes the current canonical race and races from historical shared games
  whose loadinfo evidence was reconstructed;
- analyst-authored player notes;
- behavioral/coordination inference;
- long-term materialized relationship summaries;
- scheduled/background refresh of commander caches;
- operator map layers/annotations from the second external-tools workstream.

The next acceptance step after merge is a production deploy and a concrete
current-game commander drill-down proving the UI path from a peer summary back
to public game ids and reconstructed turn-overlap intervals.
