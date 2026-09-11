# Planets Intel — Current Handoff

Updated: 2026-09-11

GitHub is the source of truth. Active development remains on `feature/operational-ui`. A fresh chat must inspect the actual branch HEAD before making current-code claims or writes, then read this file together with `NEW_CHAT_START.md`, `PROJECT_STATE.md` and the newest dated handoff under `docs/handoff/`.

## Repository / runtime

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production backend image embeds the React/Vite frontend.
- Deployment entrypoint: `/opt/planets-intel/scripts/deploy/production.sh`
- Never infer production HEAD from chat history; inspect it before every deploy.

Source/runtime checkpoint at this handoff:

```text
feature/operational-ui
d93fce4df17d25376f7c98ac98eed02253ce68f4
```

Production was deployed successfully at that exact SHA on 2026-09-11:

```text
Build: OK
Backend tests: OK (289)
DB: 0018_tow_target_ship_id (head)
Backend recreate: OK
Health: {"status":"ok","service":"planets-intel-backend"}
DEPLOY OK
Log: /opt/planets-intel/logs/deploy/20260911-223653-production.log
```

Detailed checkpoint: `docs/handoff/2026-09-11-turn-review-blockers-production.md`.

## Current product state

### Private intel ingestion / refresh

The earlier stale-map incident was traced to a stale `PLANETSNU_PROXY_URL`, not to malformed historical requests from this project. Private sync was restored after the proxy was corrected.

Current safety behavior:

- total accessible-private refresh failure is surfaced to the frontend even when the refresh endpoint itself returns HTTP 200;
- concrete server failure detail is retained for the user-facing warning;
- if canonical game turn and factual private snapshot turn differ, current-turn private fact tables fail closed instead of relabelling stale facts as current;
- the mismatch warning names both turns;
- the map may still show the factual stale snapshot because the map labels its snapshot turn explicitly.

The stale-turn warning is deployed. An intentionally reproduced browser mismatch has not yet been recorded as separate visual acceptance.

### Historical / provenance behavior

Historical mode is read-only and uses stored turn-indexed evidence. Current mutable metadata is not silently substituted for historical state where a historical snapshot does not exist.

Combined intel preserves source/batch/turn provenance and uses the freshest-known factual value per field. Visual aggregation must never rewrite factual recipient or observer provenance.

### Communications

Communications are considered CLOSED absent regression:

- canonical private grouping and race-first labels were browser/runtime-confirmed;
- Robots (`spaceshepherd`) showed 3 messages in the acceptance case;
- unresolved root `#7649938` renders as `Message`, not `Reply`;
- visual thread merge must not change factual recipient provenance.

### Turn Review / movement provenance

The first production Turn Review / evidence ledger is deployed. It uses the existing unified movement pipeline rather than a parallel simulator and keeps factual observations, local planning state and derived movement output separate.

Movement rows now expose why an endpoint is UNKNOWN through structured blocker provenance:

- `phase_state_required` — the formula is supported, but the factual state at that Host phase is not available;
- `implementation_gap` — the rule is supported by the lab evidence but has not yet been integrated safely into this production path;
- `missing_fact` — a required factual input is missing or unknown;
- `dependency_unresolved` — the row depends on an earlier unresolved movement result;
- `order_ambiguity` — Host ordering/target selection is ambiguous;
- `unsupported_host_rule` — the applicable Host behavior remains outside the supported model.

The blocker classification is provenance metadata only. It must never turn an uncertain endpoint into a certain one.

### Movement / local order drafts

A unified movement-prediction pipeline already exists. Do not rebuild it from scratch.

Relevant implementation includes:

- `movement_turn_state.py`
- `movement_prediction.py`
- `movement_prediction_runtime.py`
- `movement_prediction_unified_runtime.py`
- `movement_prediction_blockers.py`
- Tow / Move Most / Intercept phase services
- local ship / planet / starbase order drafts
- frontend movement-prediction API, map hook, prediction state and draft panels.

Facts, local drafts and derived predictions remain separate. Prediction output is explicitly non-Host-final.

Tow draft browser acceptance is still pending for:

1. save an explicit Tow target;
2. confirm drafted target precedence over factual `mission1target`;
3. confirm `PREDICTED TOW` / `PREDICTED TOWED` rendering;
4. confirm switching away from Tow clears the local Tow target and that Tow + Intercept remains rejected.

### Movement research reconciliation

The adjacent research repository `Numillyash/planets-lab` is the evidence source for reconstructed Host mechanics. At this checkpoint its `main` was:

```text
2cfad9f5de83e052afc420179f45ab22557cec4f
```

The latest compiled-corpus checkpoint records two production-relevant movement conclusions.

Base finite-fuel Tow movement in ordinary Classic/Nu scope is supported as:

`DOCUMENTED + CORPUS_OBSERVED + TESTED + DIFF_VERIFIED`.

The cleaned historical discriminator supports post-Alchemy combined tower+towed movement mass and proportional insufficient-fuel movement.

Important production boundary: this does **not** automatically make every finite-fuel Tow prediction safe in IntelBoard. The product still must know the actual Tow-phase fuel state. Snapshot neutronium is not automatically movement-phase neutronium. Finite-fuel Tow therefore remains fail-closed when that phase-aligned state is unavailable.

For normal movement, the lab evidence also supports the continuous nominal one-turn fuel basis for true-partial Move Most / Intercept as:

`CORPUS_OBSERVED + TESTED + DIFF_VERIFIED`.

Production still keeps the old true-partial shortage guard. It is now classified as an `implementation_gap`, not as an unknown formula. Do not remove the guard until the production path preserves the exact Host major/minor projection and the verified continuous one-turn fuel leg without weakening phase-state safety.

Finite-fuel Intercept likewise has a supported fuel formula, but snapshot neutronium is not automatically Intercept-phase fuel. Those withheld endpoints are `phase_state_required` rather than evidence that the formula is unknown.

Tow contests/chains/cycles, web-hit interruption details and other special interactions remain separately scoped and must not be smuggled into the base rule.

### Battle Planner / combat rules

Two previously stale IntelBoard formulas were independently rechecked against immutable downloaded historical games in `planets-lab`, then corrected and deployed:

- Federation recovery: `min(100 - damage, shield + 25)`;
- native planet beam tech: nearest-integer `ROUND(SQRT(DP / 2))`.

Cross-repo corpus recheck:

- Federation: corrected 48/48 vs old 38/48; 10 corrected-only discriminators; 0 old-only;
- native beam tech: corrected 1036/1036 vs old 712/1036; 324 corrected-only discriminators; 0 old-only.

The corrected rules are isolated in `battle_simulator_verified_rules.py` and exercised by dedicated regression tests.

Do not infer that the whole Host combat orchestration is solved. Low-level combat resolution is materially advanced, while engagement selection/order/side assignment and several Host-order interactions remain research work in `planets-lab`.

### Threat / military intelligence

The existing product already contains useful intelligence infrastructure and should be extended rather than replaced:

- threat analysis from historical mass, VCR-revealed weapons and constrained loadout hypotheses;
- attack-group / target-planet context;
- defender and starbase context;
- military score attribution;
- deterministic post-combat replay state where inputs are sufficient;
- analyst-confirmed state layered separately from factual observations.

Inference must remain visibly distinct from facts.

## Immediate product priorities

1. Use the deployed Turn Review blocker classes to identify and close the highest-value `implementation_gap` cases without weakening fail-closed behavior.
2. Integrate the lab-verified true-partial normal-movement fuel path only with the exact Host major/minor projection and verified continuous nominal one-turn fuel basis; preserve missing/phase-state boundaries.
3. Complete the pending Tow draft browser acceptance.
4. Extend analyst/threat UX using existing provenance and prediction layers rather than inventing new factual state.
5. Keep product work independent from ongoing `planets-lab` Host combat-order reverse. Do not wait for full NuHost reconstruction before improving provenance, review and analyst UX.

## Working rules

- GitHub branch state is authoritative; documentation SHA examples are checkpoints, not permission to skip inspection.
- A successful HTTP request is not proof that all per-account sync work succeeded.
- Known zero != unknown; missing != zero.
- Fact != inference != simulation != local draft.
- Current fact != historical fact.
- Combat-time evidence != current ship state.
- Hull capacity != factual current weapons.
- Snapshot fuel != automatically movement-phase fuel.
- Unsupported Host behavior fails closed.
- Do not deploy documentation-only commits merely to make production match docs.
