# Planets Intel — Current Handoff

Updated: 2026-08-15

This file is the exact session/runtime handoff for starting a completely fresh development chat. Read it together with `docs/architecture/PROJECT_STATE.md`, then inspect the actual current GitHub branch HEAD and server checkout before changing or deploying code.

## Repository / deployment

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- GitHub branch HEAD immediately before this handoff update: `52fc51e04a159dea3121198d16c7b419badb3ff1` (`feat: reconcile VCR fighter losses with military delta`).
- Server checkout: `/opt/planets-intel`
- Backend health: `http://127.0.0.1:18080/api/health`
- Docker Compose services include `backend` and `postgres`.
- The production backend image also builds/copies the React/Vite frontend, so `docker compose build backend` validates frontend TypeScript/Vite compilation as well as the backend image.
- Old Git on server: prefer `git symbolic-ref --quiet --short HEAD` instead of `git branch --show-current`.

### Current deployment gap

The last explicitly shown runtime behavior still corresponds to code around `384dfca`: the deployed hull source list contained only `mobile/app/play`, and the Military panel did not yet contain the newer VCR attribution/reconciliation UI.

GitHub `feature/operational-ui` is materially ahead of that runtime. Important commits after the last deployed behavior include:

1. `18e7e5e` — attach factual VCR equipment evidence to combat events.
2. `4b8c92b` — type VCR combat equipment evidence in frontend history models.
3. `f8f95cf` — show VCR fighter evidence in scoreboard.
4. `e82a23f` — surface combat fighter evidence in scoreboard.
5. `0a76549` — make Planets.nu artwork fetching resilient.
6. `29af36e` — capture IntelBoard handoff.
7. `a72272f` — refresh project state for clean handoff.
8. `c91d677` — add final clean-chat bootstrap.
9. `8664605` — classify VCR fighter deltas for military analysis.
10. `52fc51e` — reconcile review-confirmed VCR fighter losses with turn-to-turn Military attribution while suppressing snapshot overlap.

No GitHub Actions workflow/status was available for `52fc51e`; therefore the newest frontend changes are **not build-validated yet**. The next server deploy must run `docker compose build backend` before the new behavior is considered runtime-validated.

Recommended first command block:

```bash
cd /opt/planets-intel

git fetch origin
printf 'BRANCH: '; git symbolic-ref --quiet --short HEAD || true
printf 'HEAD:   '; git log -1 --oneline
printf 'DIVERGENCE HEAD...origin: '; git rev-list --left-right --count HEAD...origin/feature/operational-ui
git status --short

docker compose ps
curl -fsS http://127.0.0.1:18080/api/health && echo
```

If the working tree is clean and HEAD is behind:

```bash
git pull --ff-only origin feature/operational-ui

docker compose build backend >/tmp/pi-build.log 2>&1 \
  && echo 'BUILD: OK' \
  || { echo 'BUILD: FAILED'; tail -80 /tmp/pi-build.log; exit 1; }

docker compose up -d --force-recreate backend >/dev/null
sleep 2
curl -fsS http://127.0.0.1:18080/api/health && echo
```

## Confirmed runtime facts

### Upstream outage fallback

Planets.nu public API was unavailable through the configured route during the previous runtime session. The dashboard originally failed with `Planets.nu game list is unavailable` / `No games available` even though canonical data already existed locally.

This was fixed so the account game list falls back to canonical DB membership (`PlanetsAccount -> GamePlayerSlot -> Game`). It was verified live while upstream was unavailable:

```text
UPSTREAM: UNAVAILABLE
#683330 | Bernices Sector | T4  | canonical-cache
#682909 | Chanda M Sector | T12 | canonical-cache
#682932 | Estes Sector | T8  | canonical-cache
#680933 | Mekbuda Sector | T46 | canonical-cache
#683230 | Organia 3 Sector | T4  | canonical-cache
#683335 | Ceros Sector | T1  | canonical-cache
```

`/games/{id}` also has a canonical fallback using `Game`, `GameRuleCatalog.settings`, `GamePlayerSlot`, latest `ScoreObservation` and latest `PlayerTurnActivityObservation`. It was verified for game `682909`:

```text
SOURCE: canonical-cache
GAME: 682909 Chanda M Sector T12 Running
MAP: 800 x 800
FOF: 2 active=0 increment=5
PLAYERS: 8
slot 1 gandolf       planets=9  ships=8  bases=1 ready=True
slot 2 haco_fried    planets=9  ships=10 bases=1 ready=True
slot 3 georgul       planets=1  ships=4  bases=0 ready=True
slot 4 nekot         planets=10 ships=13 bases=1 ready=True
slot 5 helping die   planets=14 ships=8  bases=3 ready=True
slot 6 rodrox        planets=6  ships=5  bases=1 ready=False
slot 7 tusilat       planets=10 ships=13 bases=1 ready=True
slot 8 mussoleni ii  planets=10 ships=11 bases=1 ready=True
CACHE GAME DETAILS: OK
```

Do not fabricate missing cached fields. If a value is not persisted canonically, use `null`/empty unavailable presentation rather than a false zero.

### Ammo / hidden-loadout semantics

Hard invariant:

```text
known zero != unknown
```

Verified combined factual view in game `682909` for observer `helping die`:

```text
#22 owner=5 hull=69 ammo=0  fighters=UNKNOWN source=2
#43 owner=5 hull=69 ammo=45 fighters=UNKNOWN source=2
#62 owner=5 hull=69 ammo=25 fighters=UNKNOWN source=2
#63 owner=7 hull=94 ammo=UNKNOWN fighters=UNKNOWN source=None
```

The frontend was visually verified before the newest commits:

- Own Super Star Destroyer shows `Fighter bays 3`, `Fighters 45`.
- Enemy Rush shows `Fighter bays 10`, but does **not** show `Fighters 0`.

Rules:

- Generic Nu `ammo` is a factual value on an observer's own ship.
- For an enemy private ship row, `ammo=0` can be an undisclosed placeholder and must not become factual zero.
- Only interpret generic `ammo` as fighters/torpedoes when hull/equipment knowledge proves the ammunition type.
- VCR combat equipment is a separate combat-time evidence layer. It must not overwrite current ship state.
- Combined/shared intel must preserve source/provenance before deciding whether ammo is disclosed.

### Military Δ intelligence — last deployed screenshot

For Rebel player `tusilat`, T11 -> T12, the last deployed screenshot showed:

```text
Public Δ Military:      +29,004
Public Δ warships:      +2
Confirmed factual Δ:    0
Unattributed remainder: +29,004
Observed fighter stock: 0 fighters
Carrier loads known:    0
Carrier loads unknown:  2
```

Carrier evidence visible in that screenshot:

- Ship #45, Gemini Class Transport, 1 fighter bay — current fighters UNKNOWN.
- Ship #63, Rush Class Heavy Carrier, 10 fighter bays — current fighters UNKNOWN.

Newly observed combat hulls shown:

- #21 PL21 Probe — hull-only Military floor 135.
- #45 Gemini Class Transport — hull-only floor 520.
- #63 Rush Class Heavy Carrier — hull-only floor 3,275.

The panel correctly states that newly observed does not prove newly built and hull-only floors exclude engines, weapons and ammunition.

## VCR equipment and Military attribution now in GitHub

Raw accessible VCR observations expose immutable combat-start equipment through normalized event-side `combat_equipment`, including beams, launchers, fighter bays, torpedo/fighter counts, shield, damage, crew, mass and race ID. The read layer is scoped to accessible linked accounts and does not mutate canonical observations.

Two additional commits now implement the next attribution step:

### `8664605` — classify in-host fighter deltas

`CombatFighterEvidencePanel` now distinguishes:

- **review-confirmed in-host delta**: combat-start VCR fighter count plus `analyst_confirmed_vcr_review` post-combat fighter state;
- **deterministic-replay delta**: derived replay result, displayed separately and explicitly not factual;
- unresolved rows where no post-combat fighter state exists.

The panel aggregates review-confirmed and replay-only fighter/Military deltas by owner. Absolute VCR combat-start loads remain combat-time evidence only and never become current ship loadout.

### `52fc51e` — reconcile VCR fighter loss with score attribution

`MilitaryAttributionPanel` now fetches combat events for the exact public-score turn and applies a conservative overlap rule:

1. If a carrier has factual fighter counts in both previous and current combined snapshots, its turn-to-turn fighter delta already contains any combat loss. Any review-confirmed VCR fighter delta for that ship is marked **overlap** and contributes `0` additional Military.
2. If no directly comparable turn snapshot exists for that ship, an `analyst_confirmed_vcr_review` combat-start -> post-combat fighter delta is time-compatible with that host and is added to `Confirmed factual Δ` at `125 Military / fighter`.
3. `deterministic_vcr_replay` is never included in `Confirmed factual Δ`; it remains explanatory/derived evidence.
4. VCR absolute combat-start fighter count is never treated as a previous-turn or current-turn loadout fact.

The Scoreboard now contains a `Combat fighter Δ reconciliation` section that states whether each analyst-confirmed VCR side was counted or suppressed as snapshot overlap.

This logic is present in GitHub but **has not yet been built or visually validated on `/opt/planets-intel`**.

### Relevant tactical test data

Primary live test game: `682909`, Chanda M Sector, Turn 12.

Important players:

- `helping die` — Evil Empire, slot 5.
- `tusilat` — Rebels, slot 7.
- `georgul` — Birds, slot 3; useful linked observer/intel source.

Confirmed Evil Empire fighter stock used to validate ammo semantics:

```text
SSD #43: 45 fighters
SSD #62: 25 fighters
SSD #22:  0 fighters
starbases: 10 + 5 + 5 fighters
```

Total confirmed current EE fighters in those facts: 90.

User-provided external combat simulation result (not yet verified by our battle engine): a minimally equipped Gorbie vs Rush was approximately 50% at 80 fighters, 75% at 90, 95% at 100. Keep this as analyst/user input, not a canonical game fact.

## Planets.nu artwork state

Hull #69 successfully cached on the last shown server run:

```text
RESULT: OK
CACHE: /app/private_assets/hulls/69.png
```

Hull #94 failed under the then-deployed downloader because all `mobile/app/play` candidates timed out.

GitHub code from `0a76549` onward changes the artwork downloader substantially:

- direct public route first and configured proxy second;
- adds `https://planets.nu/...` hull and planet sources;
- keeps `hulls3d/{id}_p.png` portraits before classic artwork;
- limits concurrent artwork source attempts with a semaphore of 2;
- increases timeout/read budget;
- distinguishes direct vs proxy failures.

The resilient downloader is still not runtime-validated in the shown handoff. After deploying current branch HEAD, re-test hulls 69 and 94 before making additional asset changes.

Useful diagnostic:

```bash
docker compose exec -T backend python - <<'PY'
import asyncio
from app.services.private_asset_cache import ensure_hull_asset, _hull_sources

async def main():
    for hull_id in (69, 94):
        print(f'\n===== HULL {hull_id} =====')
        for source in _hull_sources(hull_id):
            print(' ', source)
        try:
            path = await ensure_hull_asset(hull_id)
        except Exception as exc:
            print('RESULT: ERROR')
            print(type(exc).__name__, str(exc))
        else:
            print('RESULT:', 'OK' if path else 'NOT FOUND')
            if path:
                print('CACHE:', path)

asyncio.run(main())
PY
```

## War-state diagnostic

`backend/app/scripts/war_state_dump.py` exists for compact factual game snapshots and is preferable to screenshots/large console dumps for tactical analysis.

Typical invocation:

```bash
mkdir -p logs/war-state
OUT="logs/war-state/game-682909-helping-die-vs-tusilat-$(date +%Y%m%d-%H%M%S).json"

docker compose exec -T backend \
  python -m app.scripts.war_state_dump \
    682909 "helping die" "tusilat" \
  > "$OUT"

echo "SAVED: $OUT"
```

## Immediate next actions

Do these in order in a fresh chat or after reconnecting to the server:

1. Inspect `/opt/planets-intel` branch/HEAD/dirty state and compare with `origin/feature/operational-ui`.
2. If safe, fast-forward to the actual GitHub HEAD, run `docker compose build backend`, recreate backend and verify health.
3. Re-test hull #94 using the resilient downloader.
4. Open `Scoreboard -> Military Δ intelligence` for `tusilat`, T11 -> T12, and validate the new VCR sections from `8664605` and `52fc51e`.
5. Verify all four invariants in the live UI:
   - Rush #63 current fighters remain `UNKNOWN` unless a genuine current factual observation exists;
   - VCR combat-start fighters are labelled combat-time evidence only;
   - deterministic replay fighter changes are derived and never enter `Confirmed factual Δ`;
   - analyst-confirmed VCR fighter delta is counted only when no comparable T11/T12 fighter snapshot already covers that ship.
6. If no analyst-confirmed post-combat fighter state exists for the relevant `tusilat` VCRs, do **not** expect VCR fighter points in Confirmed factual Δ; validate the classification UI first and decide whether the relevant combat state should be analyst-reviewed.
7. Once runtime validation is clean, return to Battle Planner / movement fuel / Tow work according to `PROJECT_STATE.md`.

## New-chat rule

Do not reconstruct implementation state from old chat memory. Treat GitHub as source of truth. A fresh chat should explicitly read:

- `docs/architecture/NEW_CHAT_START.md`
- `docs/architecture/PROJECT_STATE.md`
- `docs/architecture/CURRENT_HANDOFF.md`

Then inspect the actual branch HEAD and the real server checkout before making further changes.
