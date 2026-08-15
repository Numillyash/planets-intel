# Planets Intel — Project State

This file is the compact handoff snapshot for continuing development across chat/session boundaries. Keep it current and short; Git history is the detailed log.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, read-time inference, historical analysis, order drafting, simulation and eventually upstream turn submission.
- UI direction: Planets-style fullscreen starmap + operational dashboard; avoid returning to the old card-heavy map UI.

## Done / stable baseline

- Linked Planets.nu accounts and game picker with deep-linked `/intelboard/<observer>/<game>` routes.
- Public loadinfo/loadscores history and scoreboard charts.
- Private loadturn ingestion and combined multi-account intel.
- Fullscreen Pixi starmap with Planets-style hull artwork cache and operational entity panes.
- Historical ship tracks with lifecycle splitting for reused ship IDs.
- VCR storage, deterministic NuHost classic replay and visual replay UI.
- Post-combat factual/replay state propagation.
- Local ship order drafts (warp/waypoint/intercept) and entity order draft scaffolding.
- Move Most predictor, Chained Intercept predictor and persistent order-vector rendering.
- Planet warp-well movement substep, including post-intercept warp wells.
- Planet navigation-link rounding compatible with displayed Planets navigation distance.
- Intercept uncertainty visualization: target sighting, standard target envelope and possible direction sector.
- Public Planets.nu GET requests honor configured proxy; transport failures are classified instead of leaking generic HTTP 500.

## In progress

- Military-score delta attribution in the Scoreboard.
  - Exact/factual attribution only for directly comparable observations across adjacent turns.
  - Mobile fighters, base fighters, planet/base defense and minefield deltas.
  - Current observed fighter stock.
  - Newly observed combat hull evidence with hull-only Military floor; never equate newly observed with newly built.
  - Unattributed remainder remains explicit instead of inventing hidden assets.

## Next

1. Validate Military Δ attribution against live game T11→T12 data (especially Rebel `tusilat`).
2. Add combat/battle planner on top of deterministic VCR replay for counter-fleet planning (Rush vs Dark Wing/Gorbie sequences).
3. Add movement fuel model using factual engine, mass/cargo/fuel and game settings.
4. Add Tow resolution ahead of Move Most/Intercept in the movement pipeline.
5. Consolidate movement phases into a single `ShipPrediction`/turn-review model.
6. Expand draftable missions/cargo/planet/starbase orders.
7. Implement explicit reviewed upstream Planets.nu write adapter, turn submission and post-host reconciliation.

## Important invariants

- Facts, inferred data and simulations are separate layers. Never overwrite facts with inference.
- Preserve provenance for combined/shared intel.
- Read-time inference should be reproducible from stored facts + rule catalog.
- Reused numeric ship IDs are not sufficient identity; lifecycle changes must use factual hull/ownership evidence.
- Local drafts never mutate canonical observations and are never sent upstream without an explicit future write-path action.
- Unknown Host behavior is fail-closed: expose uncertainty rather than invent a deterministic answer.
- Newly observed is not the same as newly built.
- Historical displacement above `warp²` can be legitimate because of planetary warp-well pull.

## Validation protocol

For routine deploys, report only:

```text
HEAD: <commit>
BUILD: OK
TESTS: OK
MIGRATIONS: OK / N/A
HEALTH: OK
RESULT: <brief UI/behavior observation>
```

On failure, preserve the full log on the host/repository and paste only the failing command plus roughly the final 30–80 relevant lines.
