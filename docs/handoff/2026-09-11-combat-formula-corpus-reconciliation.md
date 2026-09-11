# Combat formula corpus reconciliation — 2026-09-11

This checkpoint records a cross-repository reconciliation between the production Battle Planner formulas in `planets-intel` and the independently validated historical NuHost corpus in `planets-lab`.

GitHub remains the source of truth. The historical recheck is preserved in `Numillyash/planets-lab` by PR #50 (`diagnostics: recheck Intel combat formulas against corpus`) and was run against all 12 cached `/game/loadall` archives.

## Runtime corpus gate

Server runtime:

```text
candidate  3e101d6303de29998bebdc067bce55050405a016
archives   12
stages     inputs/tooling/corpus-recheck/summary all 0/0
result     all_assertions_pass=true
```

The gate deliberately compared the then-current `planets-intel` formulas with the corrected candidates rather than merely replaying the current `planets-lab` implementation.

## Federation between-fight shield recovery

Old IntelBoard candidate:

```text
recovered = round-ish 25% of missing shields
```

Corpus-verified rule:

```text
next_shield = min(100 - damage, shield + 25)
```

Runtime counts:

```text
comparable                    48
corrected exact               48
old Intel exact               38
old Intel mismatch            10
corrected-only discriminators 10
observed recovery rows        20
old-only counterexamples       0
```

Examples include factual `84 -> 100`, `80 -> 100`, `36 -> 61`, `40 -> 65`, `65 -> 90`, `55 -> 80` and `79 -> 100`. The old percentage interpretation misses the discriminator rows while the fixed +25 rule matches all 48 comparable Federation transitions.

Evidence status for this scoped rule remains:

```text
CORPUS_OBSERVED + TESTED + DIFF_VERIFIED
```

## Native planet beam tech

Old IntelBoard candidate:

```text
TRUNC/FLOOR-like sqrt(DP / 2)
```

Corpus-verified rule:

```text
ROUND(SQRT(DP / 2))
```

using nearest-integer rounding and clamping to tech 1..10 for positive defense-post counts.

The ordinary planet-beam promotion excludes special/campaign/Horwasp-heavy game `591478`.

Runtime counts:

```text
comparable                     1036
corrected exact                1036
old Intel exact                 712
old Intel mismatch              324
corrected-only discriminators   324
old-only counterexamples          0
payload conflicts                 0
unique VCRs                    6469
```

Observed discriminator examples include DP `5 -> beam 2`, `13 -> 3`, `30 -> 4`, `49 -> 5`, `67 -> 6`, `86 -> 7`, and `148 -> 9`.

Evidence status for this ordinary scoped rule is:

```text
CORPUS_OBSERVED + TESTED + DIFF_VERIFIED
```

## IntelBoard implementation change

The production Battle Planner facade now installs the corpus-verified rules at runtime while the large simulator module is being decomposed:

- Federation sequence recovery uses fixed +25 points capped by `100 - damage`;
- native planet beam tech uses nearest-integer `ROUND(SQRT(DP/2))`;
- dedicated regression tests include historical discriminator values, not only non-discriminating cap cases.

The facade approach is intentional: `battle_simulator_runtime.py` already owns the authoritative runtime overrides while `battle_simulator.py` is decomposed. The stale legacy helper bodies should not be treated as authoritative runtime mechanics.

## Scope boundary

This reconciliation changes only these two already-differential-verified mechanics. It does not promote unresolved Host combat ordering, deterministic right-side balance, Galactic Power side assignment, damaged-starbase hidden persistence, or other campaign/special mechanics.
