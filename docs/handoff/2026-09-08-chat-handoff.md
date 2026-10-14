# Chat handoff — 2026-09-08

GitHub is the source of truth. Active development remains on `feature/operational-ui`.

## Runtime/source checkpoint

Latest **runtime-confirmed production code HEAD**:

```text
f3d807faef4ef763d4898f91d3b27faaa319d52e
ui: show race-first private conversation labels
```

User-provided production deploy result for this exact HEAD:

```text
Updated to f3d807faef4ef763d4898f91d3b27faaa319d52e
Host prerequisites: OK
HEAD: f3d807faef4ef763d4898f91d3b27faaa319d52e
Build: OK
Tests: OK
Ran 289 tests
OK
DB before: 0018_tow_target_ship_id (head)
DB target: 0018_tow_target_ship_id (head)
DB after:  0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
```

Browser acceptance was also confirmed by the user for this exact code state.

A documentation commit may exist after `f3d807f`; do **not** infer that documentation-only commits were deployed. Always inspect actual GitHub HEAD and `/opt/planets-intel` runtime before changing code.

## Communications — runtime-confirmed state

### Private reply safety

Commit `4f064ce078ab63014d21271371959e712fb1e905` changed unresolved private-thread replies to fail safe in the UI. If the exact factual participant set for a Planets.nu thread is not resolved, IntelBoard must not fabricate a threaded reply. It falls back to a new private message to selected roster recipients.

The backend guard remains authoritative: a private threaded reply requires factual thread-root provenance and exact private participant resolution.

### Canonical private conversation grouping

Commit `48164eadca31e4fd29d9643d51f776b8d20f6759` canonicalizes private conversation identity to the game roster/player slot before grouping. Different representations such as username, username-with-race, account id and slot id collapse to one private conversation when uniquely resolvable.

Important invariant: canonical visual grouping does **not** promote participant provenance across different Planets.nu thread roots. Reply-vs-new-message safety is decided per factual thread root, not per merged visual channel.

This is now **runtime/browser confirmed**. In the user's production Communications view, historical `spaceshepherd (The Robots)` activity and the newer `spaceshepherd` root appear in one Direct Messages channel with 3 messages.

### Race-first channel labels

Commit `f3d807faef4ef763d4898f91d3b27faaa319d52e` changes canonical Direct Message channel labels to race-first roster labels using the factual roster `race_id` and the shared `raceName()` helper. Examples:

```text
Robots (spaceshepherd)
Evil Empire (cheeblet)
Robots (spaceshepherd) + Colonies (helping die)
```

Do not parse race names out of raw activity display strings for canonical channel identity. The roster is authoritative when uniquely resolved.

This change is **runtime/browser confirmed**: the user's production view shows `Robots (spaceshepherd) · 3`, while the canonical grouping remains intact.

Raw message author labels inside message cards remain upstream activity display strings such as `spaceshepherd (The Robots)` or `helping die (The Colonies)`; this is expected and separate from canonical conversation labeling.

### Thread #7649938

The user attempted to answer Planets.nu thread `#7649938`. Exact participants were not factually resolved by stored thread provenance, so IntelBoard correctly refused to create a true threaded reply and sent a new private root instead. The official Planets.nu UI may visually merge roots by peer; IntelBoard mirrors that visual behavior while preserving thread-level reply provenance.

Runtime maintenance output after canonical merge:

```text
activity_id: 7649938
parent_id: 0
turn: 30
scope: 3
visibility_source: ingame_activity
outgoing_recipient_player_ids: null
source_id: 179236
source_name: spaceshepherd (The Robots)
target_id: 37542
target_name: helping die (The Colonies)
message: Hey, I think we should win this together!
raw_replycount: 0
raw_replies_count: 0
```

No child rows were returned by the maintenance query.

Browser acceptance after `f3d807f` confirms that this root still shows **Message**, not **Reply**, even though it is visually grouped into `Robots (spaceshepherd)`. This is the desired fail-closed result.

Maintenance helper:

```bash
cd /opt/planets-intel
bash scripts/maintenance/activity-thread.sh 7649938
```

## Diplomacy / Share Intel

Planets.nu diplomacy is still read-only in IntelBoard. Commit `54418c008cfe50dbb59974e912464a5ce0a3bae0` makes this explicit in the UI.

Do not guess upstream relation serialization. Before implementing Share Intel / Safe Passage / Full Alliance writes, capture one verified official-client `/game/save` request after changing a relation, preserving field names and the complete `Relation...` value while redacting API/save keys and tokens. Then implement an explicit reviewed write adapter with post-write reconciliation.

Dashboard account-to-account Intel sharing is a separate IntelBoard feature and must not be confused with Planets.nu diplomacy relations.

## Movement / finite-fuel Intercept checkpoint

Current production factual population contains only unlimited-fuel games for the latest observer/game groups, so historical `planets-lab` archives remain the evidence source for finite-fuel behavior.

Important historical Intercept cases:

```text
620636 / T60 / ship44 (Gemini)
- snapshot fuel 1 KT
- candidate full cost 3 KT
- geometry without fuel does not match
- proportional fuel-proration endpoint exactly matches factual endpoint
- after fuel 0
- no known mine/storm/damage/Tow/Chunnel explanation
=> strong support that finite-fuel Intercept can prorate movement.

360690 / T69 / ship391 (Biocide)
- snapshot fuel 64 KT, candidate cost 66 KT
- factual endpoint equals full geometry, not snapshot-fuel prorated endpoint
- minimum Intercept-phase fuel compatible with factual endpoint is 66 KT
- later fuel is larger
=> pre-Host snapshot neutronium is not guaranteed to equal Intercept-phase fuel.

620694 / T73 / ship278 (Nova)
- true partial route: target distance ~82.855 > nominal warp9 max 81
- snapshot fuel 29 KT, after fuel 0
- no known mine/storm/damage/Tow/Chunnel explanation
- projected integer one-turn endpoint fuel cost = 71
- continuous nominal 81-ly cost = 72
- factual endpoint is reproduced by denominator 72, not 71
=> evidence favors fuel cost based on the continuous nominal leg before Host endpoint rasterization for a true partial route, but this is still insufficient alone for production promotion.
```

A prior diagnostic incorrectly treated `NormalMovePlan.partial` as equivalent to `waypoint_distance > effective_max_distance`; this was corrected conceptually. In planner semantics, `partial` can also mean a reachable waypoint shortened by fuel shortage.

The fast diagnostic for the next research step is:

```text
tools/diagnostics/partial_move_fuel_cost_move_most_audit.py
```

It prefilters true geometric partial Move Most candidates before unpacking archive/prepared-state data. Prefer it over the old broad audit if the latter again runs silently for minutes.

Do not change production finite-fuel law without independent discriminating evidence.

## Immediate next priorities

1. **Communications canonical merge and race-first labeling are closed/runtime-confirmed.** Do not spend more time on them unless a regression appears.
2. Continue finite-fuel movement reconstruction in `Numillyash/planets-lab`, starting from the fast `partial_move_fuel_cost_move_most_audit.py` diagnostic and the companion fuel handoff.
3. Keep unsupported finite-fuel Intercept/Tow phase state fail-closed; do not promote a law from one discriminating case.
4. Implement real Planets.nu diplomacy writes only after capturing a verified official-client `/game/save` relation request.
5. Resume broader IntelBoard roadmap after the finite-fuel evidence pass or when a higher-priority production regression appears.

## Working-thread durability rule

The active ChatGPT thread can hit an opaque product-level maximum length; there is no reliable percentage measurement of remaining thread length. Do not invent percentages.

At the end of substantive chat responses, report only one qualitative state:

```text
Состояние чата: новый / нормальный / длинный / пора обновить handoff
```

Before a major new stage, or once the thread becomes noticeably long, refresh this durable GitHub handoff before continuing. GitHub remains the recovery source of truth for opening a normal new chat after any product thread limit.

## New-chat bootstrap

Fresh chat should read, in order:

### `Numillyash/planets-intel` — `feature/operational-ui`

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. `docs/handoff/2026-09-08-chat-handoff.md`

### `Numillyash/planets-lab` — `main`

1. `docs/handoff/2026-09-05-new-chat-context.md`
2. `docs/handoff/2026-09-08-intel-fuel-chat-handoff.md`
3. `docs/ROADMAP.md`
4. `docs/COMPILED_CORPUS.md`
5. `docs/ARCHITECTURE.md`
6. `docs/WORKFLOW.md`

Then inspect actual GitHub HEADs and production runtime before changing code.
