# Planets Intel — Project State

This is the durable architectural handoff for `Numillyash/planets-intel`. Git history is the detailed implementation log. For the exact latest runtime/deploy state, also read `docs/architecture/CURRENT_HANDOFF.md`.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, read-time inference, historical analysis, order drafting, simulation and eventually explicit reviewed upstream turn submission.
- UI direction: Planets-style fullscreen starmap + operational dashboard; map-first workflow, not the old card-heavy UI.
- Source of truth across chats: GitHub repository + these handoff docs. Do not reconstruct current implementation from chat memory.
- Current implementation focus: finish real-data Battle Planner combat-model validation, currently planet/starbase multi-wave carryover, before returning to movement fuel/Tow work.

## Stable baseline

- Linked Planets.nu accounts and game picker with deep-linked `/intelboard/<observer>/<game>` routes.
- Public loadinfo/loadscores ingestion, score history, scoreboard and activity tracking.
- Private loadturn ingestion and combined multi-account intel with provenance.
- Fullscreen Pixi starmap with operational entity panes and cached Planets.nu hull/planet artwork.
- Historical ship tracks with lifecycle splitting for reused numeric ship IDs.
- VCR storage, deterministic NuHost Classic replay and visual replay UI.
- Post-combat factual/replay state propagation and host-event enrichment.
- Local ship order drafts and entity-order scaffolding.
- Move Most, chained Intercept, persistent order vectors and uncertainty rendering.
- Planet warp-well movement substep, including post-intercept warp wells.
- Planet navigation-link rounding compatible with displayed Planets navigation distance.
- War-state diagnostic: `backend/app/scripts/war_state_dump.py`.
- Communications UI with public/private channels and verified true Planets.nu threaded replies using `/game/sendmessage` + factual `parentid`.
- Battle Planner with separate combatant sources, editable simulation loadouts, deterministic replay, odds and sequential-wave queues.

## Availability / offline-read architecture

IntelBoard must not become unusable just because Planets.nu public endpoints or the configured proxy are temporarily unavailable.

Implemented:

- Public Planets.nu GET requests honor the configured proxy and classify transport failures.
- Account game list falls back to canonical DB membership (`PlanetsAccount -> GamePlayerSlot -> Game`).
- `/games/{id}` falls back to canonical `Game`, `GameRuleCatalog`, `GamePlayerSlot`, latest `ScoreObservation` and latest `PlayerTurnActivityObservation`.
- Cached responses are marked as `canonical-cache`.
- Missing cached facts remain unavailable/null; never manufacture zeroes or false current values.

The exact live verification and known upstream-outage behavior are recorded in `CURRENT_HANDOFF.md`.

## Ammo / loadout semantics

Hard invariant:

```text
known zero != unknown
```

- Generic Nu `ammo` is factual for an observer's own ship.
- Enemy private rows can contain hidden zero placeholders; those values must not become factual ammo/fighter zero.
- Interpret generic `ammo` as fighters or torpedoes only when hull/equipment knowledge proves the ammunition type.
- Combined/shared intel decides disclosure using provenance of the contributing observation.
- VCR equipment is a separate factual evidence layer at combat time; it does not automatically become current ship state.
- UI visibly distinguishes known `0` from `UNKNOWN`/unavailable.
- Battle Planner exposes simulation controls up to factual hull capacity, but analyst-entered loadout values remain simulation assumptions.

## Military-score delta attribution

The Scoreboard contains a factual lower-bound attribution model with public Military delta, warship delta, directly comparable mobile/starbase fighter deltas, defense/minefield components where factual, current observed fighter stock, hull-only floors for newly observed combat hulls, combat-start VCR fighter evidence, analyst-confirmed in-host deltas, deterministic replay as derived evidence only, and explicit unattributed remainder.

Rules:

- Unknown or hidden equipment is never guessed.
- Newly observed is not the same as newly built.
- A hull-only floor is explanatory evidence, not automatically a contribution to public turn delta.
- New/first-seen carriers are not directly comparable across turns.
- A combat-start fighter count proves only the load at that VCR instant.
- Deterministic replay remains a derived layer and never enters `Confirmed factual Δ`.

## Combat / VCR evidence

Raw accessible VCR observations can expose immutable combat-start equipment/state such as beams, launchers, torpedo type/count, fighter bays/fighters, shield, damage, crew, mass and race ID.

This evidence is attached read-time to normalized combat events with explicit evidence basis and does not mutate canonical observations. Replay-derived post-combat state remains separate from factual/analyst-confirmed state.

### Deterministic replay checkpoint

Current real-data regression result:

```text
145 unique stored VCRs
145 deterministic replays supported
0 unsupported
0 observer payload conflicts
2 analyst-confirmed checks
2 analyst matches
0 analyst mismatches
```

This is strong coverage of the current stored inputs, not proof that every Host special mechanic is represented.

### Real repeated-ship carryover checkpoint

`backend/app/scripts/combat_chain_regression.py` compares one deterministic terminal state with the next factual VCR start for the same surviving ship in the same game/turn/location.

Production corpus contained 42 such transitions. All observed transitions matched exactly for:

```text
damage
crew
torpedoes
fighters
shield (all observed repeated-chain cases were non-Federation)
```

There are currently no repeated Federation ship-chain transitions in the corpus, so Federation between-fight shield recovery remains modelled/documented but not empirically validated by a real chain.

### Planet/starbase multi-wave validation

Current exact planet carry model is in `backend/app/services/battle_simulator_planet.py`.

It models only mechanics precise enough to reproduce exactly:

- drained shield carry;
- proportional planet-defense damage;
- starbase fighters consumed before generated planet fighters;
- one additional planet DP removed per lost generated planet fighter;
- re-derived planet beams/bays/fighters/mass;
- explicit fail-closed boundary when a surviving starbase takes hull damage and exact persistent base state cannot be derived.

Read-only real-data diagnostic:

```text
backend/app/scripts/combat_planet_chain_regression.py
```

For non-starbase worlds it attempts exact next-VCR prediction only after an inferred starting planet state reproduces the first factual VCR. Starbase hidden state is never guessed.

## Battle Planner

Battle Planner is an active frontend/backend feature built on the deterministic combat engine.

Runtime-validated capabilities include:

- LEFT/RIGHT combat queues;
- ship-vs-ship and fixed RIGHT planet/starbase scenarios;
- sequential-wave combat;
- deterministic visual battle replay and multi-battle odds;
- race/crew/advantage-sensitive simulation controls;
- separate `Known ships`, `Known planets`, `Generic ship / planet` add sources;
- known ships grouped by race;
- support-ship picker filtering with explicit fallback toggle;
- known ships with zero installed weapons can still be configured up to hull capacity for simulation;
- generic hull race grouping from factual rule-catalog membership;
- editable simulation loadout without mutating factual intel;
- queue reorder, side swap and multi-combatant append.

The support-ship classifier remains a picker heuristic only:

```text
launchers > 0 OR fighter bays > 0 OR beams >= 4
```

It must never become factual combat inference.

The old picker/editor runtime-validation checklist and legacy combined-picker cleanup are complete. `BATTLE_PLANNER_HANDOFF_2026-08-25.md` now records the closed checkpoint rather than pending validation.

One observed `Battle sequence odds failed: 502 Proxy Error` remains deliberately deferred. The presence of `10000` battles in that screenshot is correlation only, not a confirmed cause.

## Communications write semantics

The current game-message write path preserves the verified Planets.nu contract.

Root/public/private message and true threaded reply both use:

```text
POST /game/sendmessage
```

Threaded reply adds:

```text
parentid=<factual thread root activity id>
```

Replying to a reply stays attached to the same factual root. Private participant sets are validated and reconciliation checks the observed parent relation. This path is runtime-validated and should not be reopened without new evidence.

## Artwork cache

- Preferred hull portrait source is Planets.nu `hulls3d/<id>_p.png`, classic hull artwork as fallback.
- Artwork fetching does not make the API proxy a hard dependency.
- Missing artwork attempts are concurrency-limited.

## Movement state

Implemented:

- Move Most predictor.
- Intercept and chained Intercept.
- Unresolved Intercept range envelope instead of a false deterministic line.
- Standard target movement envelope uses observed Warp.
- Tow/HYP/Chunnel excluded from standard movement envelope until explicitly modeled.
- Warp wells as post-movement transform; chained Intercept uses post-well final position.
- Ambiguous multiple warp wells fail closed.

Still pending after the combat checkpoint:

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
- `0` is never a placeholder for unknown tactical information.
- Hull capacity means capability, not factual installed loadout.
- UI picker filtering never deletes or reinterprets stored intel.

## Next priorities

The exact first action is always taken from `CURRENT_HANDOFF.md`. Current order:

1. Sync/deploy the actual `feature/operational-ui` HEAD if the server checkout is clean and behind.
2. Run real planet/starbase multi-wave carryover diagnostic and classify any mismatches/fail-closed cases.
3. Continue targeted Battle Planner special-combat validation only where factual/rule evidence exists; keep unexercised mechanics explicitly unvalidated.
4. Add movement fuel model.
5. Add Tow resolution ahead of Move Most/Intercept.
6. Consolidate movement phases into a unified prediction/turn-review model.
7. Expand draftable missions/cargo/planet/starbase orders.
8. Continue explicit reviewed Planets.nu write adapters with post-write reconciliation.

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

On failure, preserve the full log on the host and paste only the failing command plus roughly the final 30–80 relevant lines.
