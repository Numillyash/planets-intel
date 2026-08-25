# Planets Intel — Project State

This is the durable architectural handoff for `Numillyash/planets-intel`. Git history is the detailed implementation log. For the exact latest runtime/deploy state, also read `docs/architecture/CURRENT_HANDOFF.md`.

## Active development

- Branch: `feature/operational-ui`
- Product direction: private Planets.nu operational client with factual intel, read-time inference, historical analysis, order drafting, simulation and eventually explicit reviewed upstream turn submission.
- UI direction: Planets-style fullscreen starmap + operational dashboard; map-first workflow, not the old card-heavy UI.
- Source of truth across chats: GitHub repository + these handoff docs. Do not reconstruct current implementation from chat memory.
- Current implementation focus: Battle Planner combatant selection/loadout UX and runtime validation on top of the deterministic combat engine.

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
- Communications UI with public/private channels and verified true Planets.nu threaded replies using `/game/sendmessage` + factual `parentid`.
- Battle Planner with queue simulation, known/manual combatants, sequential waves, race/advantage handling and current separated add-source/loadout editor work.

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
- Battle Planner can expose controls up to factual hull capacity, but an analyst-entered simulated loadout is not promoted to factual current equipment.

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
- combat-start VCR fighter evidence kept separate from current loadout;
- analyst-confirmed in-host fighter deltas with snapshot-overlap suppression;
- deterministic replay deltas displayed as derived evidence only;
- explicit unattributed remainder.

Rules:

- Unknown or hidden equipment is never guessed.
- Newly observed is not the same as newly built.
- A hull-only floor is explanatory evidence, not automatically a contribution to public turn delta.
- New/first-seen carriers are not directly comparable across turns.
- An absolute combat-start fighter count proves only the load at that VCR instant; it is not a previous-turn or current-turn loadout fact.
- A VCR start -> post fighter delta may enter factual turn attribution only when the post state is analyst-confirmed and the same ship does not already have a directly comparable previous/current fighter snapshot covering the change.
- Deterministic VCR replay remains a derived layer and never enters `Confirmed factual Δ`.

## Combat / VCR evidence

Raw accessible VCR observations can expose immutable combat-start equipment such as:

- beams and beam count;
- launcher count and torpedo type/count;
- fighter bays and fighters;
- shield, damage, crew and mass;
- race ID.

This evidence is attached read-time to normalized combat events with explicit evidence basis and does not mutate canonical observations. Replay-derived post-combat state remains a separate derived layer. Analyst-reviewed post-combat state is separately stored and can support time-compatible factual attribution without converting combat-time evidence into current state.

## Battle Planner

Battle Planner is no longer only a future goal; it is an active frontend/backend feature built on the deterministic combat engine.

Current capabilities include:

- LEFT/RIGHT combat queues;
- ship-vs-ship and fixed RIGHT planet/starbase scenarios;
- sequential-wave combat;
- deterministic visual battle replay and multi-battle odds runs;
- race/crew/advantage-sensitive simulation controls;
- known ships and known planets materialized from factual/intel data;
- generic/manual combatants for scenario assumptions;
- editable simulation loadout without mutating factual intel.

Current UX work from 2026-08-25:

- add-combatant source split into `Known ships`, `Known planets`, `Generic ship / planet`;
- known ships grouped by owner race;
- low-armament support ships hidden from the default picker with an explicit `Show support ships` toggle;
- ship editor renders weapon controls using hull capacity even if the selected/observed setup currently has zero installed weapons;
- concrete validation target: `VIRGO CLASS BATTLESTAR #19`, which previously showed `0B · 0T · 8 bays` and exposed no beam editor despite a beam-capable hull.

The support-ship classifier is a picker heuristic only:

```text
launchers > 0 OR fighter bays > 0 OR beams >= 4
```

It must never become factual combat inference. It needs live review for specialty combat hulls with low armament.

Exact implementation/runtime validation instructions are in:

```text
docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md
```

## Communications write semantics

The current game-message write path preserves the verified Planets.nu contract.

Root/public/private message:

```text
POST /game/sendmessage
```

Threaded reply:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Replying to a reply stays attached to the same factual root. Private participant sets are validated and reconciliation requires the new observed activity to have the expected parent relation.

The user has runtime-validated this reply path as working. Contract details are in `docs/architecture/COMMUNICATIONS_REPLY_CONTRACT.md`.

## Artwork cache

- Current preferred hull portrait source is Planets.nu `hulls3d/<id>_p.png`, with classic hull artwork as fallback.
- Artwork fetching must not make the API proxy a hard dependency: current code tries direct public artwork routes and then configured proxy routes.
- Missing artwork attempts are concurrency-limited so one hull cannot saturate the proxy/downloader.
- Exact latest runtime validation is in `CURRENT_HANDOFF.md` / Git history when relevant.

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
- Hull capacity means capability, not factual installed loadout.
- UI picker filtering must never delete or reinterpret stored intel.

## Next priorities

The exact first actions for the next chat are in `CURRENT_HANDOFF.md`. Current order:

1. Sync/deploy the actual `feature/operational-ui` HEAD if the server checkout is clean and behind.
2. Runtime/browser-validate the new Battle Planner source picker and hull-capacity weapon editor, starting with Virgo #19 and at least one second affected hull.
3. Fix actual picker/editor regressions; verify support-ship filtering does not hide important specialty combat hulls without an accessible fallback.
4. Remove dead legacy combined-picker state after the new path is confirmed.
5. Add focused coverage for picker grouping/filtering and editor visibility where practical.
6. Continue Battle Planner combat-model validation and remaining Host mechanics.
7. Add movement fuel model.
8. Add Tow resolution ahead of Move Most/Intercept.
9. Consolidate movement phases into a unified prediction/turn-review model.
10. Expand draftable missions/cargo/planet/starbase orders.
11. Continue explicit reviewed Planets.nu write adapters with post-write reconciliation.

## New-chat bootstrap

A completely fresh chat should start by reading:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. `docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md`

Then inspect `feature/operational-ui` HEAD and server divergence before making any code change.

Suggested opening request:

```text
Работаем с Numillyash/planets-intel. GitHub — source of truth. Открой feature/operational-ui и сначала прочитай docs/architecture/NEW_CHAT_START.md, docs/architecture/PROJECT_STATE.md, docs/architecture/CURRENT_HANDOFF.md и docs/architecture/BATTLE_PLANNER_HANDOFF_2026-08-25.md. Затем проверь актуальный HEAD репозитория и состояние /opt/planets-intel. Продолжай с Immediate next actions из CURRENT_HANDOFF.md: сначала runtime/browser validation новых Battle Planner picker/editor изменений. Старый чат не используй как источник текущего состояния.
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
