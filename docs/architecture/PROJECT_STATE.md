# Planets Intel — Project State

This is the durable architectural handoff for `Numillyash/planets-intel`. Git history is the detailed implementation log. For the exact latest runtime/deploy state, also read `docs/architecture/CURRENT_HANDOFF.md`.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, read-time inference, historical analysis, order drafting, simulation and eventually explicit reviewed upstream turn submission.
- UI direction: Planets-style fullscreen starmap + operational dashboard; map-first workflow, not the old card-heavy UI.
- Source of truth across chats: GitHub repository + these handoff docs. Do not reconstruct current implementation from chat memory.

## Stable baseline

- Linked Planets.nu accounts and game picker with deep-linked `/intelboard/<observer>/<game>` routes.
- Public loadinfo/loadscores ingestion, score history, scoreboard and activity tracking.
- Private loadturn ingestion and combined multi-account intel with provenance.
- Fullscreen Pixi starmap with operational entity panes and cached Planets.nu hull/planet artwork.
- Historical ship tracks with lifecycle splitting for reused numeric ship IDs.
- VCR storage, deterministic NuHost classic replay and visual replay UI.
- Post-combat factual/replay state propagation and host-event enrichment.
- Local ship order drafts and entity-order scaffolding.
- Move Most, chained Intercept, persistent order vectors and uncertainty rendering.
- Planet warp-well movement substep, including post-intercept warp wells.
- Planet navigation-link rounding compatible with displayed Planets navigation distance.
- War-state diagnostic: `backend/app/scripts/war_state_dump.py`.

## Availability / offline-read architecture

IntelBoard must not become unusable just because Planets.nu public endpoints or the configured proxy are temporarily unavailable.

Implemented:

- Public Planets.nu GET requests honor the configured proxy and classify transport failures.
- Account game list falls back to canonical DB membership (`PlanetsAccount -> GamePlayerSlot -> Game`).
- `/games/{id}` falls back to canonical `Game`, `GameRuleCatalog`, `GamePlayerSlot`, latest `ScoreObservation` and latest `PlayerTurnActivityObservation`.
- Cached responses are marked as `canonical-cache`.
- Missing cached facts must remain unavailable/null; never manufacture zeroes or false current values.

The exact live verification and known upstream-outage behavior are recorded in `CURRENT_HANDOFF.md`.

## Ammo / loadout semantics

This is a hard invariant:

```text
known zero != unknown
```

- Generic Nu `ammo` is factual for an observer's own ship.
- Enemy private rows can contain hidden zero placeholders; those values must not become factual ammo/fighter zero.
- Interpret generic `ammo` as fighters or torpedoes only when hull/equipment knowledge proves the ammunition type.
- Combined/shared intel decides disclosure using provenance of the contributing observation.
- VCR equipment is a separate factual evidence layer at combat time; it does not automatically become current ship state.
- UI must visibly distinguish known `0` from `UNKNOWN`/unavailable.

This behavior is verified for own Super Star Destroyers and enemy Rush data in live game `682909`; exact examples are in `CURRENT_HANDOFF.md`.

## Military-score delta attribution

The Scoreboard contains a factual lower-bound attribution model:

- public Military delta and warship delta;
- directly comparable mobile fighter delta;
- starbase fighter delta;
- planet/base defense delta;
- minefield delta where facts exist;
- current observed fighter stock;
- carrier fighter evidence with known/unknown coverage;
- newly observed combat hulls with hull-only Military floors;
- explicit unattributed remainder.

Rules:

- Unknown or hidden equipment is never guessed.
- Newly observed is not the same as newly built.
- A hull-only floor is explanatory evidence, not automatically a contribution to public turn delta.
- New/first-seen carriers are not directly comparable across turns.

Current GitHub code additionally attaches factual VCR combat-start equipment to combat events and has Scoreboard UI for VCR fighter evidence. This must remain separate from current private loadout state. Runtime validation status is in `CURRENT_HANDOFF.md`.

## Combat / VCR evidence

Raw accessible VCR observations can expose immutable combat-start equipment such as:

- beams and beam count;
- launcher count and torpedo type/count;
- fighter bays and fighters;
- shield, damage, crew and mass;
- race ID.

This evidence is attached read-time to normalized combat events with explicit evidence basis and does not mutate canonical observations. Replay-derived post-combat state remains a separate derived layer.

Longer-term goal: build a Battle Planner on top of the deterministic VCR engine, including sequential-wave combat and explicit scenario assumptions for unknown enemy equipment.

## Artwork cache

- Current preferred hull portrait source is Planets.nu `hulls3d/<id>_p.png`, with classic hull artwork as fallback.
- Artwork fetching must not make the API proxy a hard dependency: current code tries direct public artwork routes and then configured proxy routes.
- Missing artwork attempts are concurrency-limited so one hull cannot saturate the proxy/downloader.
- Exact last runtime validation (including hull #69 success and hull #94 failure before the latest resilience change) is in `CURRENT_HANDOFF.md`.

## Movement state

Implemented:

- Move Most predictor.
- Intercept and chained Intercept.
- Unresolved Intercept range envelope instead of a false deterministic line.
- Standard target movement envelope uses observed Warp.
- Tow/HYP/Chunnel are excluded from the standard movement envelope until explicitly modeled.
- Warp wells are a post-movement transform; chained Intercept uses the post-well final position.
- Ambiguous multiple warp wells fail closed.

Still pending:

- fuel model;
- Tow resolution;
- unified movement phase / `ShipPrediction` turn-review model.

## Important invariants

- Facts, inferred data and simulations are separate layers. Never overwrite facts with inference.
- Preserve provenance for combined/shared intel.
- Read-time inference must be reproducible from stored facts + rule catalog.
- Reused numeric ship IDs are not sufficient identity; lifecycle changes require factual hull/ownership evidence.
- Local drafts never mutate canonical observations and are never sent upstream without an explicit future write-path action.
- Unknown Host behavior is fail-closed: expose uncertainty rather than invent a deterministic answer.
- Newly observed is not the same as newly built.
- Historical displacement above `warp²` can be legitimate because of planetary warp-well pull.
- A historical/combat-time fact is not automatically a current fact.
- `0` must never be used as a placeholder for unknown tactical information.

## Next priorities

The exact first actions for the next chat are in `CURRENT_HANDOFF.md`. After syncing/deploying the actual branch HEAD, priorities are:

1. Validate the newest VCR fighter-evidence Scoreboard changes against live T11 -> T12 `tusilat` data.
2. Re-test Rush hull #94 artwork using the current resilient downloader.
3. Decide which VCR evidence can safely explain Military delta without turning combat-time evidence into current state.
4. Build Combat/Battle Planner on top of the deterministic VCR engine.
5. Add movement fuel model.
6. Add Tow resolution ahead of Move Most/Intercept.
7. Consolidate movement phases into a unified prediction/turn-review model.
8. Expand draftable missions/cargo/planet/starbase orders.
9. Implement explicit reviewed Planets.nu write adapter, turn submission and post-host reconciliation.

## New-chat bootstrap

A completely fresh chat should start by reading:

1. `docs/architecture/PROJECT_STATE.md`
2. `docs/architecture/CURRENT_HANDOFF.md`

Then inspect `feature/operational-ui` HEAD and server divergence before making any code change.

Suggested opening request:

```text
Работаем с Numillyash/planets-intel. Открой branch feature/operational-ui, сначала прочитай docs/architecture/PROJECT_STATE.md и docs/architecture/CURRENT_HANDOFF.md, затем проверь текущий HEAD репозитория. Считай GitHub источником истины и продолжай с Immediate next actions из CURRENT_HANDOFF.md. Старый чат не используй как источник состояния проекта.
```

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
