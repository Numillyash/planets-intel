# Tow draft browser acceptance — 2026-09-12

## Scope

This checkpoint records browser/runtime acceptance of the explicit Tow-target draft workflow in the production IntelBoard, plus one map-rendering defect discovered during that acceptance.

Production under test was the successfully deployed runtime:

```text
f5c9ab9bfcc3c9c5bb32f2bbf7a5f0f3340e0ced
```

The GitHub development branch already contained a documentation-only merge after that runtime; do not interpret a later documentation SHA as a separately deployed product build.

## Browser acceptance case

The user exercised the Orders panel on current factual intel with a Lizard Class Cruiser and at least one visible colocated Tow candidate.

Observed behavior:

1. Switching the draft mission to `Try to Tow` exposed a dedicated `Tow target` selector.
2. The upstream Tow target was absent in the acceptance case, while an explicit colocated target was selected locally. `Save draft` became available.
3. After saving, the panel remained in `Local draft orders`, retained the selected Tow target, and the map emitted a deterministic `PREDICTED TOW · 81.0 ly · W9` vector. Because no upstream Tow target existed, this is browser evidence that the saved explicit draft target, not factual `mission1target`, drove the Tow prediction.
4. A factual refresh happened after the draft base batch and the UI surfaced `Factual snapshot changed after this draft was saved.` rather than silently relabelling the draft as current.
5. Switching to `Exploration` removed the Tow-target row and returned the map to an ordinary `PREDICTED MOVE` presentation.
6. Switching to `Intercept` exposed `Intercept target`, removed the Tow-target control, and showed the Intercept lock/sight overlays. No Tow + Intercept combined draft was presented.
7. Returning to `Try to Tow` restored the Tow-specific editor path.

Accepted from this run:

- explicit visible-colocated Tow-target selection;
- saving the explicit Tow target;
- local drafted-target precedence in the no-upstream-target case;
- mission-switch clearing of the Tow-specific editor;
- Tow/Intercept mutual exclusion in the UI;
- tower-side `PREDICTED TOW` rendering;
- stale-draft provenance warning after factual refresh.

## Rendering defect discovered

The browser image contained overlapping vector text near the Tow route, so `PREDICTED TOWED` could not be visually accepted from the production build.

Inspection of `frontend/src/features/map/orderVectorScene.ts` found a stronger concrete defect: movement prediction rows were rendered only while iterating ships that themselves had a local draft. A normal Tow target usually has no local draft of its own, even though the backend prediction response contains a `phase=tow`, `tow_role=target` row for it. Therefore the target prediction could be silently omitted from the map.

The same path also rendered the draft-route label and deterministic prediction label on top of each other, explaining part of the observed text overlap.

The fix on `fix/tow-prediction-rendering`:

- renders all prediction-response items independently from the local-draft iteration;
- keeps Intercept lock/sight rendering tied to the drafted interceptor;
- suppresses the redundant `DRAFT` label when that ship already has a renderable deterministic prediction;
- offsets paired Tow tower/target labels so coincident routes can show both `PREDICTED TOW` and `PREDICTED TOWED` legibly.

## Acceptance state

Tow draft acceptance is **substantially complete but not fully closed** at this checkpoint.

Closed:

- target selection/save;
- drafted-target use in prediction;
- mission-switch behavior;
- Tow/Intercept exclusion;
- tower prediction rendering.

Pending after deploying the rendering fix:

- one browser confirmation that both `PREDICTED TOW` and `PREDICTED TOWED` are separately visible for the same Tow pair.

This visual defect does not change the backend Tow prediction result or promote uncertain Host mechanics. Finite-fuel Tow must still fail closed whenever Tow-phase fuel state is not factual.
