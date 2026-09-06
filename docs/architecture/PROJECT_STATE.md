# Planets Intel — Project State

This is the durable architectural handoff for `Numillyash/planets-intel`. Git history is the detailed implementation log. For the exact latest runtime/deploy state, also read `docs/architecture/CURRENT_HANDOFF.md`.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, read-time inference, historical analysis, order drafting, simulation and eventually explicit reviewed upstream turn submission.
- UI direction: Planets-style fullscreen starmap + operational dashboard; map-first workflow, not the old card-heavy UI.
- Source of truth across chats: GitHub repository + these handoff docs. Do not reconstruct current implementation from chat memory.
- Current implementation focus: complete explicit local Tow-target drafting on top of the runtime-validated strict Tow integration, then continue toward finite-fuel Intercept and unified turn movement prediction.

## Stable baseline

- Linked Planets.nu accounts and game-centric chooser with deep-linked `/intelboard/<observer>/<game>` routes.
- Automatic discovery/private refresh for newly appearing active games.
- Public loadinfo/loadscores ingestion, score history, scoreboard and activity tracking.
- Private loadturn ingestion and combined multi-account intel with provenance.
- Fullscreen Pixi starmap with operational entity panes and cached Planets.nu hull/planet artwork.
- Historical ship tracks with lifecycle splitting for reused numeric ship IDs.
- VCR storage, deterministic NuHost Classic replay and visual replay UI.
- Post-combat factual/replay state propagation and host-event enrichment.
- Local ship, planet and starbase order drafts.
- Move Most, chained Intercept, persistent order vectors and uncertainty rendering.
- Planet warp-well movement substep, including post-intercept warp wells.
- Fuel-aware ordinary movement with factual movement-mass reconstruction and verified Nu proportional insufficient-fuel rule.
- Strict owner-visible Tow resolution integrated ahead of Move Most / Intercept for the supported unlimited-fuel subset.
- Planets.nu communications UI with verified true threaded replies using `/game/sendmessage` + factual `parentid`.
- Battle Planner with separate combatant sources, editable simulation loadouts, deterministic replay, odds and sequential-wave queues.

## Hard semantic invariants

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
missing data != zero
hull capacity != factual installed weapons
```

Additional operational rules:

- deterministic replay is derived evidence, never a factual observation;
- local drafts never mutate canonical observations;
- unsupported Host behavior fails closed rather than leaking a plausible-looking deterministic endpoint;
- reused numeric ship IDs are not sufficient identity without factual lifecycle evidence;
- picker filtering never deletes or reinterprets stored intel.

## Availability / offline-read architecture

IntelBoard must remain usable when Planets.nu public endpoints or the configured proxy are temporarily unavailable.

Implemented:

- public Planets.nu GET requests honor the configured proxy and classify transport failures;
- account game list falls back to canonical DB membership;
- `/games/{id}` falls back to canonical `Game`, `GameRuleCatalog`, slots and latest score/turn activity observations;
- cached responses are marked as `canonical-cache`;
- missing cached facts remain unavailable/null rather than manufactured zeroes.

## Combat / Battle Planner

The current deterministic combat checkpoint is materially closed on the available corpus. Runtime/UI support includes ship-vs-ship, planet/starbase scenarios, sequential waves, visual replay, odds, editable assumptions and explicit evidence-source precedence.

Known evidence gaps remain explicit and must not be guessed:

- Federation damaged-start weapon continuity;
- Federation 25% between-fight shield recovery;
- repeated no-starbase planet carry;
- hidden starbase persistent state after hull damage;
- right-side carrier +360 probabilistic balance rule.

Do not reopen the Battle Planner picker/editor UX without new evidence.

## Ammo / loadout semantics

- Generic Nu `ammo` is factual for an observer's own ship.
- Enemy private rows can contain hidden zero placeholders; those values must not become factual ammo/fighter zero.
- Interpret generic `ammo` as fighters or torpedoes only when hull/equipment knowledge proves the ammunition type.
- VCR equipment is factual at combat time only and does not automatically become current ship state.
- Hull weapon capacity is simulation capability, not factual fitted loadout.

## Movement state

### Implemented

- Move Most geometry.
- Classic and chained Intercept.
- Unresolved Intercept range envelope instead of a false deterministic line.
- Standard target movement envelope from observed Warp.
- Planetary warp-well post-transform with ambiguous multi-well fail-closed behavior.
- Factual movement-mass reconstruction from hull/equipment/cargo components.
- Nu movement fuel factor + documented truncation formula.
- Verified proportional insufficient-fuel distance and Host integer coordinate projection for the supported normal-movement subset.
- Strict factual Tow lock primitives.
- Tow chain isolation so unrelated Tow components remain independently decidable.
- Tow integrated ahead of Move Most / Intercept in the request-local runtime.
- Known post-Tow target positions are visible to later Intercept.
- Tow participants with unresolved outcomes are withheld from later movement instead of receiving false ordinary endpoints.
- Movement-prediction API/frontend types expose `phase: tow` and Tow metadata.
- Map rendering labels known Tow routes as `PREDICTED TOW` / `PREDICTED TOWED`.

### Runtime Tow checkpoint

Production read-only audit on the deployed strict integration found:

```text
29 latest factual observer/game groups
29 unlimited-fuel groups
25 factual owner Tow missions
25 targets visible
25/25 strict locked
0 uncertain
0 same-target contest groups
0 Tow chain groups
```

This validates the present factual unlimited-fuel Tow population against the strict production lock subset. It does not validate finite-fuel Tow.

### Deliberate fail-closed boundaries

Remain unresolved unless stronger evidence is added:

- finite-fuel Tow: Tow-phase neutronium + combined tower/target physical mass and ordering;
- Tow + planetary warp-well propagation;
- same-target Tow winner identity;
- Tow chains/cycles ordering;
- zero-fuel and unsupported Gravitonic shortage combinations outside the verified normal-fuel subset;
- finite-fuel Intercept ordering/consumption;
- HYP/Chunnel/mine/web/storm interactions in the production turn predictor unless explicitly modeled.

## Current draft-model gap

`ShipOrderDraft` currently stores only `intercept_target_ship_id`; there is no `tow_target_ship_id`.

Therefore a local draft that newly changes a ship to `Try to Tow` is intentionally unresolved rather than silently reusing an old factual `mission1target`.

The next Tow product change must add a deliberate Tow target field end-to-end:

```text
Alembic migration
-> ShipOrderDraft model
-> Pydantic request/response
-> service validation/serialization
-> API route
-> frontend type/API state
-> Tow target picker
-> movement runtime uses drafted target
```

Do not overload `intercept_target_ship_id` for Tow.

## Communications write semantics

Verified true threaded reply contract:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Reply-to-reply remains attached to the same factual root. Do not reopen Communications without new evidence.

## Artwork cache

- Preferred hull portrait source is Planets.nu `hulls3d/<id>_p.png`, classic hull artwork fallback.
- Artwork fetching does not make the API proxy a hard dependency.
- Missing artwork attempts are concurrency-limited.

## Next priorities

The exact first action is always taken from `CURRENT_HANDOFF.md`. Current order:

1. Add explicit `tow_target_ship_id` drafting and UI target selection.
2. Feed drafted Tow targets into strict Tow-before-Move-Most prediction with fail-closed validation.
3. Research/implement finite-fuel Intercept on the unified post-Tow movement state only where evidence is sufficient.
4. Consolidate Tow / Move Most / Intercept into unified `ShipPrediction` / turn-review output.
5. Expand draftable missions/cargo/planet/starbase orders.
6. Continue explicit reviewed Planets.nu write adapters with post-write reconciliation.

## New-chat bootstrap

A fresh chat starts by reading:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. `docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md`

Then inspect `feature/operational-ui` HEAD and server divergence before any change.

## Validation protocol

For routine deploys:

```text
HEAD: <commit>
BUILD: OK
TESTS: OK
MIGRATIONS: OK / N/A
HEALTH: OK
RESULT: <brief runtime/UI/diagnostic observation>
```

On failure, preserve the full log on the host and paste the failing command plus roughly the final 30–80 relevant lines.
