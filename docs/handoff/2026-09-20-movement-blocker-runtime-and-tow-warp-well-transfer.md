# 2026-09-20 — Current movement blocker runtime and unlimited-Tow warp-well transfer

GitHub remains the source of truth. This checkpoint records the first runtime
result from the current-turn movement blocker inventory and the evidence boundary
for the next production transfer.

## Production/runtime source

The production checkout was fast-forwarded to:

```text
62cc7a9d0600ce18910ecf81244385653dceb301
```

The read-only diagnostic was then run through:

```text
bash scripts/maintenance/inspect-movement-blockers.sh
```

No production data was modified.

## Runtime blocker population

The effective movement-prediction facade returned:

```text
current_factual_groups        31
groups_with_prediction_items  14
groups_with_errors             0
prediction_items              48
predicted_items               34
unknown_items                 14
```

Every emitted row in this runtime population was a Tow participant:

```text
tow:tower  24
tow:target 24
```

Every UNKNOWN row had the same blocker:

```text
dependency_unresolved 14
```

Split by role:

```text
tow:tower  7
tow:target 7
```

The 14 rows are therefore seven Tow pairs, not fourteen independent movement
problems.

All 48 emitted rows had:

```text
fuel_status = unlimited
```

The repeated unresolved reason was:

```text
Tow lock and pre-well endpoint are known, but the Tow + planetary warp-well
interaction is not independently verified.
```

No current emitted row in this runtime inventory had:

```text
implementation_gap
phase_state_required
missing_fact
order_ambiguity
unsupported_host_rule
```

Important scope note: this inventory covers rows actually emitted by the
effective production prediction facade. In this snapshot that means Tow rows;
it is not evidence that every possible Move Most or Intercept case in all stored
games has no blockers.

## planets-lab evidence boundary

The evidence repository was checked at actual `main` HEAD:

```text
2cfad9f5de83e052afc420179f45ab22557cec4f
```

The relevant durable evidence is already present on `main`.

The finite-fuel Tow warp-well follow-up
(`docs/handoff/2026-09-09-finite-fuel-tow-warpwell-runtime.md`) consumed the
complete prior direct `phase_neither_possible` population:

```text
phase_neither_input          2585
geometry_warpwell_exact      2529
phase_warpwell_both_possible 2529
phase_warpwell_neither         56
```

Ordinary historically eligible planetary warp wells therefore explained
2529/2585 rows (~97.83%) of that bounded Tow residual population.

The same repository records ordinary warp-well ordering as
`TESTED + DIFF_VERIFIED`, route-equivalent owner-visible Tow as
`TESTED + DIFF_VERIFIED`, and the base finite-fuel Tow movement rule as
`DOCUMENTED + CORPUS_OBSERVED + TESTED + DIFF_VERIFIED`.

The September 9 handoff still blocked a general finite-fuel Tow transfer because
the Tow cost-basis discriminator and factual Tow-phase fuel state were not
available. That boundary does not apply to the current 14 runtime UNKNOWN rows:
all of them are in games whose rules provide unlimited movement fuel.

## Production transfer scope

The next transfer is intentionally narrow:

```text
strict owner-visible Tow lock
+ unlimited-fuel game
+ ordinary planetary warp-well resolver
+ unambiguous zero-or-one eligible well result
=> shared post-well endpoint for tower and target
```

Implementation reuses the existing production `resolve_warp_well()` result. It
does not invent a second well algorithm.

The pre-well Tow endpoint remains preserved separately in prediction metadata.

Fail-closed boundaries remain:

- finite-fuel Tow;
- unresolved Tow lock / Four Fingers fuel state;
- Tow contests, chains and cycles;
- overlapping planetary wells whose authoritative tie-break is not modelled;
- mine/web/storm/Chunnel/hyperjump ordering and other special interactions.

This transfer does not make movement output Host-final and does not turn
snapshot neutronium into phase-aligned fuel.
