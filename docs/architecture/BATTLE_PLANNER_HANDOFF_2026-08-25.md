# Battle Planner handoff — 2026-08-25 / updated 2026-08-26

GitHub is the source of truth. Continue on `Numillyash/planets-intel`, branch `feature/operational-ui`.

This handoff originally described the Battle Planner picker/editor checkpoint before runtime validation. That validation is now complete. Do **not** follow older instructions that treated Virgo/editor/picker checks or legacy-picker cleanup as pending. The exact latest runtime and diagnostic state is in `docs/architecture/CURRENT_HANDOFF.md`.

## Completed picker/editor work

Key implementation history:

```text
e30bfb170b82e6df78d21daf2fd98283f01bdfb3  fix: edit weapons by hull capacity
9b2dda5b8561c882bf4225be9e9438facba8d5c7  feat: split battle planner combatant sources
414e0bdb4a56e9235e0197f1aaa81c20b0231a20  feat: separate battle planner combatant pickers
7238dc409a22c4e06fe6958dea24a9e2abc58044  fix: keep battle picker sources horizontal
a5c34fd994a0833bb96c4f7d1c167eaf89d48830  refactor: remove legacy battle picker state
```

Runtime/browser validation confirmed:

- LEFT/RIGHT use separate `Known ships`, `Known planets`, `Generic ship / planet` sources;
- known ships are grouped by race;
- low-armament support ships are hidden by default and available through `Show support ships`;
- generic hulls are grouped using rule-catalog race hull membership;
- generic hull labels no longer contain the redundant `Manual ·` prefix;
- known ships with factual zero installed weapons can still expose simulation controls up to factual hull capacity;
- `VIRGO CLASS BATTLESTAR #19` was explicitly checked, plus a second affected hull;
- generic planet/starbase on RIGHT works and opens in the editor;
- multiple queued LEFT/RIGHT combatants, reorder and side swap work;
- deterministic and normal odds paths work;
- VCR validation-lab spacing and compact starbase layout were visually accepted;
- the legacy combined-picker state/helper code was removed without changing default queue initialization.

The support-ship filter remains presentation-only:

```text
launchers > 0 OR fighter bays > 0 OR beams >= 4
```

It must never become factual combat inference.

Hard invariant:

```text
known zero != unknown
fact != inference != simulation
hull capacity != factual installed weapons
```

## Deferred single 502 observation

One validation screenshot showed:

```text
Battle sequence odds failed: 502 Proxy Error
```

The UI happened to contain `10000` battles. This is a single observation only; it is not established that 10,000 battles are the cause or that a reproducible threshold exists.

The user explicitly deferred investigation. Later work must reproduce deliberately and inspect backend/proxy timings before changing timeouts.

## Deterministic real-VCR checkpoint

Read-only diagnostic `backend/app/scripts/combat_regression_dump.py` has been run against production data.

Confirmed result:

```text
unique VCRs:          145
replay supported:     145
replay unsupported:     0
payload conflicts:      0
analyst checks:          2
analyst matches:         2
analyst mismatches:      0
```

This is strong regression coverage for the deterministic engine, but it is not proof that every Host special mechanic is represented in the corpus.

## Real ship-chain carryover checkpoint

`backend/app/scripts/combat_chain_regression.py` compares deterministic terminal state of one VCR with factual start state of the same surviving ship in the next VCR of the same game/turn/location.

Production data contained 42 such transitions. All observed transitions matched for:

```text
damage
crew
torpedoes
fighters
shield (all observed transitions were non-Federation)
```

The first diagnostic version had a reporting-only bug where `status=match` did not increment the public `matches` key. The actual records and shield counters were correct. Fixed in:

```text
c79795cf103fcc265a4397db0928c3fb3244816f  fix: count combat chain regression statuses
0f36cf4883c2b25919770525eb25012d3052b926  test: lock combat chain summary counters
```

No repeated Federation ship chain was present, so Federation between-fight shield recovery remains unvalidated by real chain evidence.

## Current Battle Planner validation focus

The next real-data checkpoint is planet/starbase multi-wave carryover.

Current exact model in `backend/app/services/battle_simulator_planet.py`:

- carries drained shield;
- applies exact planet-defense loss for combat damage;
- consumes starbase fighters before generated planet fighters;
- converts lost generated planet fighters into additional planet-defense loss;
- re-derives beams, bays, fighters and mass;
- fails closed when a surviving starbase takes hull damage because exact post-combat base defense/tech/base-damage split is not available.

New read-only diagnostic:

```text
backend/app/scripts/combat_planet_chain_regression.py
```

It compares repeated factual planet VCRs. Exact prediction is attempted only for explicitly non-starbase worlds and only after an inferred starting planet state reproduces the factual first VCR. Starbase hidden state is not guessed.

See `CURRENT_HANDOFF.md` for the exact commit, CI and server command.

## Communications

True Planets.nu threaded replies remain validated using:

```text
POST /game/sendmessage
parentid=<factual thread root activity id>
```

Do not reopen Communications without new upstream evidence. See `COMMUNICATIONS_REPLY_CONTRACT.md`.

## Fresh-chat rule

A fresh chat must read, in order:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`
4. this file

Then inspect actual GitHub HEAD and `/opt/planets-intel` divergence before any deploy or code change.
