# Planets Intel — Current Handoff

Updated: 2026-08-15

This is the exact current handoff for a fresh development chat. GitHub is the source of truth. Read this together with `NEW_CHAT_START.md` and `PROJECT_STATE.md`, then inspect the actual branch HEAD and `/opt/planets-intel` before deploying.

## Repository / branch

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Code HEAD validated by the first CI run: `571de74c8473e104f56da17342829fb4a8a25f4e` (`ci: add backend frontend and image validation`).
- Server checkout: `/opt/planets-intel`
- Health endpoint: `http://127.0.0.1:18080/api/health`
- Production `backend` Docker image builds and embeds the React/Vite frontend.
- Server Git is old; use `git symbolic-ref --quiet --short HEAD` rather than relying on `git branch --show-current`.

The actual branch may be newer than the SHA written above because this handoff file itself is committed afterward. Always inspect GitHub HEAD first.

## CI / build status

GitHub Actions CI now exists at `.github/workflows/ci.yml`.

First run on commit `571de74` completed successfully:

```text
Backend tests:     SUCCESS
Backend compile:   SUCCESS
Frontend tsc/vite: SUCCESS
Production image:  SUCCESS
```

The production-image job builds `backend/Dockerfile`, so the current VCR/Military frontend changes have passed the same multi-stage frontend/backend image build used for deployment.

This is **not** a substitute for server runtime validation. `/opt/planets-intel`, Docker Compose health, Planets.nu connectivity, cached DB data and browser behavior still need to be checked on the real host.

## Deployment gap

The last explicitly shown server runtime was older, around `384dfca`. Evidence:

- its hull source diagnostic showed only `mobile.planets.nu`, `app.planets.nu` and `play.planets.nu`;
- its Scoreboard did not yet contain the newer VCR fighter classification/reconciliation UI.

GitHub is materially ahead of that runtime. Important commits include:

```text
18e7e5e  attach factual VCR equipment evidence to combat events
4b8c92b  type VCR combat equipment evidence in frontend history models
f8f95cf  show VCR fighter evidence in scoreboard
e82a23f  surface combat fighter evidence in scoreboard
0a76549  make Planets.nu artwork fetching resilient
c91d677  add final clean-chat bootstrap
8664605  classify VCR fighter deltas for military analysis
52fc51e  reconcile VCR fighter losses with military delta
20df052  update handoff after VCR attribution work
ff31d75  align project state with VCR delta reconciliation
571de74  add backend/frontend/production-image CI
```

### Server sync / deploy check

Run before assuming the newest code is deployed:

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

If the tree is clean, the branch is `feature/operational-ui`, local-ahead is `0`, and the checkout is behind:

```bash
git pull --ff-only origin feature/operational-ui

docker compose build backend >/tmp/pi-build.log 2>&1 \
  && echo 'BUILD: OK' \
  || { echo 'BUILD: FAILED'; tail -80 /tmp/pi-build.log; exit 1; }

docker compose up -d --force-recreate backend >/dev/null
sleep 2
curl -fsS http://127.0.0.1:18080/api/health && echo
```

## Hard intel invariants

These must survive every future change:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
```

Additional rules:

- Generic Nu `ammo` is factual for an observer's own ship.
- Enemy private rows may contain undisclosed zero placeholders; never turn those into factual ammo/fighter zero.
- Interpret generic `ammo` as fighters/torpedoes only when hull/equipment knowledge proves the ammunition type.
- Combined/shared intel must preserve provenance before disclosure decisions.
- VCR equipment is immutable combat-time evidence and must never overwrite the current ship observation.
- Deterministic replay is derived evidence, not factual observation.
- Newly observed is not the same as newly built.

## Live tactical validation game

Primary game: `682909`, Chanda M Sector, Turn 12.

Important players:

- `helping die` — Evil Empire, slot 5.
- `tusilat` — Rebels, slot 7.
- `georgul` — Birds, slot 3; useful linked observer/intel source.

Confirmed EE fighter semantics from factual current data:

```text
SSD #43: 45 fighters
SSD #62: 25 fighters
SSD #22:  0 fighters
starbases: 10 + 5 + 5 fighters
```

Total confirmed current EE fighters in those facts: 90.

Enemy Rush #63 must keep **current fighters = UNKNOWN** unless an actual current factual observation exists, even if VCR combat evidence reveals a fighter count at combat time.

## Military Δ — last old runtime observation

For Rebel `tusilat`, T11 -> T12, the last old deployed screenshot showed:

```text
Public Δ Military:      +29,004
Public Δ warships:      +2
Confirmed factual Δ:    0
Unattributed remainder: +29,004
Observed fighter stock: 0 fighters
Carrier loads known:    0
Carrier loads unknown:  2
```

Visible carrier evidence then:

- #45 Gemini Class Transport — 1 fighter bay, current fighters UNKNOWN.
- #63 Rush Class Heavy Carrier — 10 fighter bays, current fighters UNKNOWN.

Newly observed combat hulls included #21 PL21 Probe, #45 Gemini and #63 Rush. Their hull-only Military floors are explanatory evidence only; first observation does not prove construction during that turn.

## VCR fighter evidence now in GitHub

### Factual combat-start layer

Accessible raw `CombatObservation.payload` is attached read-time as `combat_equipment` on normalized combat event sides. It can include:

- beams / beam count;
- launchers / torpedo type / torpedoes;
- fighter bays / fighters;
- shield / damage / crew / mass;
- race ID.

This is immutable **combat-start** evidence. It does not mutate observations and does not become current loadout.

### `8664605` — evidence classification

`CombatFighterEvidencePanel` now separates:

- `analyst_confirmed_vcr_review` -> **review-confirmed in-host delta**;
- `deterministic_vcr_replay` -> **derived replay delta**;
- missing post state -> unresolved.

It shows start fighters, post fighters, fighter delta and corresponding `125 Military / fighter`, aggregated by owner. Replay-only deltas are visibly marked derived.

### `52fc51e` — conservative score reconciliation

`MilitaryAttributionPanel` now fetches combat events for the exact public-score turn and reconciles review-confirmed fighter losses with snapshot deltas.

Rule:

1. If the same carrier has factual fighter counts in both previous and current combined snapshots, its Tprev -> Tcur fighter delta already covers combat loss. The VCR delta is marked **overlap** and adds `0` extra Military.
2. If no directly comparable fighter snapshot exists for that ship, an `analyst_confirmed_vcr_review` combat-start -> post-combat fighter delta is time-compatible with the host and can enter `Confirmed factual Δ` at `125 Military / fighter`.
3. `deterministic_vcr_replay` never enters `Confirmed factual Δ`.
4. Absolute combat-start fighter stock never becomes a previous-turn or current-turn stock fact.

The Scoreboard now has `Combat fighter Δ reconciliation`, showing each analyst-confirmed VCR side as either:

```text
counted · no comparable turn snapshot
```

or

```text
overlap · already covered by turn snapshots
```

This code has passed CI build/tests but still needs live browser validation on game `682909` after the server is updated.

## Artwork cache

Last shown server result:

```text
Hull #69: OK
CACHE: /app/private_assets/hulls/69.png

Hull #94: ERROR
all then-deployed mobile/app/play candidates timed out
```

Current GitHub code from `0a76549` onward is newer and:

- tries direct public artwork route first, configured proxy second;
- includes `https://planets.nu/...` candidates;
- prefers `hulls3d/<id>_p.png`, with classic hull art fallback;
- limits concurrent source attempts with a semaphore of 2;
- uses larger timeout/read budgets;
- distinguishes direct and proxy failures.

Re-test after deployment:

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

Prefer the compact factual diagnostic over screenshots/huge console dumps:

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

1. Inspect `/opt/planets-intel` branch/HEAD/dirty state and compare with `origin/feature/operational-ui`.
2. Fast-forward/deploy current GitHub HEAD if safe; verify server build + health.
3. Re-test hull #94 with the resilient downloader.
4. Open `Scoreboard -> Military Δ intelligence` for `tusilat`, T11 -> T12.
5. Validate:
   - Rush #63 current fighters remain UNKNOWN;
   - VCR combat-start fighters are clearly combat-time evidence;
   - replay-only fighter changes stay derived and out of `Confirmed factual Δ`;
   - analyst-confirmed VCR delta is counted only without comparable T11/T12 snapshot overlap.
6. If the relevant VCRs have no analyst-confirmed post-combat fighter state, do not manufacture one merely to explain the score; the UI should show the evidence as unresolved/derived as appropriate.
7. After runtime validation, continue with Combat/Battle Planner, then movement fuel model, then Tow resolution according to `PROJECT_STATE.md`.

## New-chat bootstrap

A fresh chat must read, in order:

1. `docs/architecture/NEW_CHAT_START.md`
2. `docs/architecture/PROJECT_STATE.md`
3. `docs/architecture/CURRENT_HANDOFF.md`

Then inspect actual GitHub HEAD and real server checkout. Do not reconstruct current state from old chat memory.
