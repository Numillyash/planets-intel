# Chat handoff — 2026-09-08

GitHub is the source of truth. Active development remains on `feature/operational-ui`.

## Runtime/source checkpoint

Latest GitHub / deployed production HEAD confirmed by user:

```text
48164eadca31e4fd29d9643d51f776b8d20f6759
fix: merge canonical private conversations
```

User-provided production deploy result for this exact HEAD:

```text
BUILD: OK
TESTS: OK — 289
DB: 0018_tow_target_ship_id (head)
BACKEND RECREATE: OK
HEALTH: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
```

Do not infer newer server state from this file; always inspect GitHub HEAD and `/opt/planets-intel` first.

## Communications — current state

### Private reply safety

Commit `4f064ce078ab63014d21271371959e712fb1e905` changed unresolved private-thread replies to fail safe in the UI. If the exact factual participant set for a Planets.nu thread is not resolved, IntelBoard must not fabricate a threaded reply. It falls back to a new private message to selected roster recipients.

The backend guard remains authoritative: a private threaded reply requires factual thread-root provenance and exact private participant resolution.

### Canonical private conversation grouping

User then observed that a newly sent private message to `spaceshepherd` appeared as a second IntelBoard conversation because historical inbound activity was labeled `spaceshepherd (The Robots)` while the newly sent root was grouped as `spaceshepherd`.

Commit `48164eadca31e4fd29d9643d51f776b8d20f6759` fixes this by canonicalizing private conversation identity to the game roster/player slot before grouping and labeling. Different representations such as username, username-with-race, account id and slot id should collapse to one private conversation when uniquely resolvable.

Important invariant: canonical visual grouping does **not** promote participant provenance across different Planets.nu thread roots. Reply-vs-new-message safety is decided per factual thread root, not per merged visual channel.

After deployment, browser verification is still needed: the Direct Messages list should show one canonical `spaceshepherd` conversation containing both old and newly sent messages. If it still splits, inspect actual activity payloads for those records.

### Thread #7649938

The user attempted to answer Planets.nu thread `#7649938`. Exact participants were not factually resolved by the stored thread provenance, so IntelBoard correctly refused to create a true threaded reply and sent a new private root instead. The official Planets.nu UI may visually merge roots by peer; IntelBoard now mirrors that visual behavior while preserving thread-level reply provenance.

Maintenance helper available for deeper inspection:

```bash
cd /opt/planets-intel
bash scripts/maintenance/activity-thread.sh 7649938
```

## Diplomacy / Share Intel

The user attempted to enable Planets.nu `Share Intel` through the dashboard and found that nothing was sent upstream.

This is expected with current implementation: Planets.nu diplomacy is read-only in IntelBoard. Commit `54418c008cfe50dbb59974e912464a5ce0a3bae0` makes this explicit in the UI.

Do not guess the upstream relation serialization. Before implementing Share Intel / Safe Passage / Full Alliance writes, capture one verified official-client `/game/save` request after changing a relation, preserving field names and the complete `Relation...` value while redacting API/save keys and tokens. Then implement an explicit reviewed write adapter with post-write reconciliation.

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

A population audit was introduced to compare projected-endpoint vs continuous-nominal fuel-cost bases for true partial Move Most routes. The original broad audit was too slow/silent; a faster prefiltered diagnostic was added in `planets-lab` (see companion handoff there). Do not change production finite-fuel law without independent discriminating evidence.

## Immediate next priorities

1. Browser-verify canonical private conversation merge on deployed `48164ead...`.
2. If needed, inspect `activity-thread.sh 7649938` to improve factual recipient provenance without weakening reply safety.
3. Implement real Planets.nu diplomacy write only after capturing official `/game/save` relation serialization.
4. Continue finite-fuel movement research from `planets-lab`; keep unsupported finite-fuel Intercept/Tow phase state fail-closed.
5. Resume broader roadmap only after these regressions/checkpoints are closed.

## New-chat bootstrap

Fresh chat should read, in order:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. `docs/handoff/2026-09-08-chat-handoff.md`
5. companion `Numillyash/planets-lab/docs/handoff/2026-09-08-intel-fuel-chat-handoff.md`

Then inspect actual GitHub HEADs and server runtime before changing code.
