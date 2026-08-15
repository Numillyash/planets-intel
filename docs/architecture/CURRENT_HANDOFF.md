# Planets Intel — Current Handoff

Updated: 2026-08-15

This file is the exact session/runtime handoff for starting a completely fresh development chat. Read this file together with `docs/architecture/PROJECT_STATE.md`, then inspect the current Git branch before changing code.

## Repository / deployment

- Repository: `Numillyash/planets-intel`
- Active branch: `feature/operational-ui`
- GitHub branch HEAD at handoff creation: `0a76549e1ce68ff42f25c656fc7a9059be8dd5fd` (`fix: make Planets.nu artwork fetching resilient`).
- Server checkout: `/opt/planets-intel`
- Backend health: `http://127.0.0.1:18080/api/health`
- Docker Compose services include `backend` and `postgres`.
- The production backend image also builds/copies the frontend, so `docker compose build backend` validates and deploys frontend changes too.
- Old Git on server: prefer `git symbolic-ref --quiet --short HEAD` instead of `git branch --show-current`.

### Important deployment gap at handoff

The last runtime behavior shown in chat corresponds to the code around `384dfca` (the hull source list still had only `mobile/app/play`, and the Military panel did not yet show the later VCR fighter-evidence section). GitHub `feature/operational-ui` is **5 commits ahead** of `384dfca`:

1. `18e7e5e` — attach factual VCR equipment evidence to combat events.
2. `4b8c92b` — type VCR combat equipment evidence in frontend history models.
3. `f8f95cf` — show VCR fighter evidence in scoreboard.
4. `e82a23f` — surface combat fighter evidence in scoreboard.
5. `0a76549` — make Planets.nu artwork fetching resilient.

Therefore, a new chat must first verify server HEAD and pull/rebuild before assuming any of these five commits are deployed.

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

If the working tree is clean and HEAD is behind, update with:

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

Planets.nu public API was unavailable through the configured route during the last session. The dashboard originally failed with `Planets.nu game list is unavailable` / `No games available` even though canonical data already existed locally.

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

`/games/{id}` was also given a canonical fallback using `Game`, `GameRuleCatalog.settings`, `GamePlayerSlot`, latest `ScoreObservation` and latest `PlayerTurnActivityObservation`. It was verified for game `682909`:

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

This is a hard invariant now:

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

The frontend was visually verified:

- Own Super Star Destroyer shows `Fighter bays 3`, `Fighters 45`.
- Enemy Rush shows `Fighter bays 10`, but does **not** show `Fighters 0`.

Rules:

- Generic Nu `ammo` is a factual value on an observer's own ship.
- For an enemy private ship row, `ammo=0` can be an undisclosed placeholder and must not become factual zero.
- Only interpret generic `ammo` semantically as fighters/torpedoes when the hull/equipment catalog proves the ammunition type.
- VCR combat equipment is separate factual evidence at combat time. It must not overwrite current ship state.
- Combined/shared intel must preserve source/provenance before deciding whether ammo is disclosed.

### Military Δ intelligence — last deployed screenshot

For Rebel player `tusilat`, T11 -> T12:

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

GitHub now contains the five later commits listed above that attach factual VCR equipment evidence and surface VCR fighter evidence in the Scoreboard. These changes were not yet runtime-validated in the shown screenshot. First validate them after deployment before changing attribution logic further.

### Relevant game / tactical test data

Primary live test game: `682909`, Chanda M Sector, Turn 12.

Important players:

- `helping die` — Evil Empire, slot 5.
- `tusilat` — Rebels, slot 7.
- `georgul` — Birds, slot 3; this account is no longer the tactical focus, but remains a useful linked observer/intel source.

Confirmed Evil Empire fighter stock used to validate ammo semantics:

```text
SSD #43: 45 fighters
SSD #62: 25 fighters
SSD #22:  0 fighters
starbases: 10 + 5 + 5 fighters
```

Total confirmed current EE fighters in those facts: 90.

User-provided external combat simulation result (not yet verified by our battle engine): a minimally equipped Gorbie vs Rush was approximately 50% at 80 fighters, 75% at 90, 95% at 100. Keep this as analyst/user input, not a canonical game fact.

## VCR equipment evidence now in GitHub

The current branch now attaches immutable combat-start equipment from raw accessible `CombatObservation.payload` into normalized combat event sides as `combat_equipment`. Fields include beam ID/count, launcher count, bay count, torpedo ID/count, fighters, shield, damage, crew, mass and race ID, with evidence basis `vcr_combat_observation`.

The read layer is explicitly scoped by accessible linked accounts and selects the freshest accessible raw VCR observation. It does not mutate stored observations and does not convert combat-time state into current ship state.

Frontend types and Scoreboard UI were added to expose this evidence. The next validation should specifically check whether known VCR fighter counts explain part of `tusilat`'s +29,004 Military without contaminating the current carrier-load factual lower bound.

## Planets.nu artwork state

Hull #69 successfully cached on the last server run:

```text
RESULT: OK
CACHE: /app/private_assets/hulls/69.png
```

Hull #94 failed under the then-deployed downloader because all `mobile/app/play` candidates timed out.

The current GitHub HEAD `0a76549` changes the artwork downloader substantially:

- tries direct CDN route first and configured proxy second;
- adds `https://planets.nu/...` hull and planet sources;
- keeps current `hulls3d/{id}_p.png` portraits before classic artwork;
- limits concurrent artwork source attempts with a semaphore of 2;
- increases timeout/read budget;
- distinguishes direct vs proxy errors.

This HEAD is not yet runtime-validated in the handoff. After deploy, re-test hulls 69 and 94 before doing more asset work.

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

`backend/app/scripts/war_state_dump.py` exists for compact factual game snapshots. It is preferable to screenshots/console dumps for tactical analysis.

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

Do these in order in a fresh chat:

1. Inspect server branch/HEAD/dirty state and compare with `origin/feature/operational-ui`.
2. If safe, deploy current GitHub HEAD and verify build + health.
3. Re-test hull #94 with the new resilient artwork downloader.
4. Open Scoreboard -> Military Δ intelligence for `tusilat`; validate the new VCR fighter-evidence UI now present in GitHub.
5. Check that VCR evidence remains explicitly combat-time evidence and does not turn Rush #63 current fighters from UNKNOWN into a fabricated current count.
6. Decide how much of VCR evidence can contribute to turn-delta attribution. Only directly time-compatible evidence should enter `Confirmed factual Δ`; otherwise present it as explanatory evidence beside the unattributed remainder.
7. Once attribution is sound, return to Battle Planner / movement fuel / Tow work according to `PROJECT_STATE.md`.

## New-chat rule

Do not reconstruct project state from old chat memory. Treat GitHub as source of truth. In a fresh chat, explicitly read:

- `docs/architecture/PROJECT_STATE.md`
- `docs/architecture/CURRENT_HANDOFF.md`

Then inspect the actual current branch HEAD and only after that make changes.
