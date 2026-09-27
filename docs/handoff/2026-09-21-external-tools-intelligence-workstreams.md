# External Planets.nu tools — product intelligence workstreams

Date: 2026-09-21

Repository: `Numillyash/planets-intel`
Branch: `feature/operational-ui`

This note records product ideas extracted from three external Planets.nu tools. It is a planning/source-boundary record, not a claim that any feature below is already implemented.

> Expanded catalog: `docs/handoff/2026-09-27-external-planets-tools-reference-catalog.md` now records a broader client/plugin survey, licensing cautions, and an explicit `planets-intel` vs `planets-lab` responsibility matrix. This 2026-09-21 note remains the focused origin of the Commander Intelligence / map-layer workstreams.

## Sources reviewed

1. T-Continuum Analyser
   - https://analyzerplanetsnu.freeddns.org/?lang=ru
   - Relevant ideas: historical replay, player/race statistics, corpus browsing/filtering by Host/game settings.
2. chmeee.org Planets.nu tools
   - https://chmeee.org/#planets.nu
   - Relevant ideas: starmap filtering, showing messages/events spatially, map notes and compact location summaries.
3. player-affinity-tool
   - https://github.com/derblondehans/player-affinity-tool
   - Relevant implementation idea: current-game player list -> public game histories -> pairwise shared-game matrix, with event-log handling for replaced/dead players and turn-overlap calculation.

## What is actually new for IntelBoard

The existing product already has historical private snapshots, Time Machine, historical ship tracks, communications, threat analysis, VCR evidence and the operational Pixi map. Rebuilding generic replay functionality is therefore not the goal.

The missing product axis is **commander/player intelligence**: who the people in the current game are, their attributable public history, and how often/when they have previously appeared together.

## Workstream A — Commander / Player Dossier

### Factual inputs

Prefer public Planets.nu endpoints and locally cached responses:

- `/game/loadinfo?gameid=...` for player slots and public game events;
- `/games/list?username=...&status=2,3` for public player game history;
- other official public endpoints only when their semantics are documented and needed.

Never use a third-party site's derived number as a factual observation when the underlying Planets.nu data can be obtained directly.

### Replacement-aware participation

A game-level relationship must not be inferred merely because two usernames occur somewhere in the same historical game.

For each username/game pair, preserve one or more factual participation periods, using attributable event/slot metadata where available:

```text
username
game_id
slot/player id when attributable
turn_from
turn_to
source
source_event ids / provenance
confidence of interval reconstruction
```

The external affinity implementation demonstrates the useful pattern of recovering usernames for dead/replaced slots from join/drop events and intersecting participation periods. Reimplement this against our own data/provenance model rather than copying the external source.

### Pairwise factual summaries

A derived-but-non-interpretive relationship layer may expose:

```text
player_a
player_b
shared_games
games_with_actual_turn_overlap
overlapping_turn_count
first_observed_shared_game
last_observed_shared_game
per-game overlap intervals
```

These summaries are derived from factual public history and must retain links to their source games/intervals.

### Behavioral inference boundary

Do not collapse historical co-presence into a factual "alliance" claim.

Possible later inference labels may include concepts such as repeated association or likely coordination, but only in the inference layer with:

- explicit method/version;
- supporting factual observations;
- uncertainty/confidence;
- no mutation of factual relationship data.

Likewise, repeated co-presence may represent allies, opponents, replacement patterns or tournament/community structure.

### Useful dossier views

A bounded first product slice can include:

- public historical games for the selected commander;
- race history/frequency when directly attributable;
- current-game peers previously encountered;
- shared-game count;
- true overlapping-turn count;
- drill-down to the specific historical games and overlap periods.

Avoid speculative player scoring in the initial implementation.

## Workstream B — operator map layers, filtering and annotations

The old chmeee.org tools are useful primarily as UX precedent.

Candidate additions to the existing Pixi operational map:

- visibility/filter controls for factual entities, predictions, tracks, threats, messages/events and annotations;
- spatial markers for attributable events such as VCR/combat, explosions/destruction, selected messages and other location-bearing evidence;
- analyst notes anchored to a planet, ship, map coordinate or turn;
- compact location summary for multiple ships/entities at one coordinate.

Required boundary:

```text
factual map entity/event
!= derived visualization
!= analyst annotation
!= inference
!= prediction
```

Annotations must never enter combined factual intel merely because they are rendered on the same map.

## Workstream C — what not to duplicate

The T-Continuum Analyser demonstrates that bulk historical replay/statistics are useful, but IntelBoard already has the relevant product foundations:

- historical snapshots;
- Time Machine;
- historical ship tracks/lifecycle handling;
- VCR/combat evidence.

Do not create a second replay subsystem. Extend the existing historical/provenance stack where necessary.

Host-settings corpus selection belongs in `Numillyash/planets-lab`, not in this product repository.

## External-code and evidence policy

- External tools are idea/reference sources, not Host authorities.
- Third-party derived metrics are not evidence of NuHost mechanics.
- Reimplement algorithms against official/public Planets.nu observations and our own schemas.
- Do not copy third-party source code without checking that the license permits the intended use and preserving required attribution.
- Keep API/raw observation caching separate from derived commander summaries and from inference.

## Suggested implementation sequence

1. Inspect the existing public game/player ingestion and DB models; reuse them where possible.
2. Add a cached public player-history adapter rather than issuing repeated frontend fan-out requests.
3. Add normalized player participation intervals with provenance.
4. Add pairwise shared-game/turn-overlap query service and tests.
5. Expose a minimal Commander Dossier in the current game's player/race UI.
6. Only after factual/derived boundaries are stable, consider an inference layer for historical association.
7. Add map filter/event/annotation UX independently so it cannot contaminate factual intel.

The first acceptance target should be a current-game player whose historical pairwise relation can be traced from the UI all the way back to concrete public Planets.nu games and reconstructed overlapping-turn intervals.
