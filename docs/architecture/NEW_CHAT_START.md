# Planets Intel — New Chat Start

Updated: 2026-08-15 19:06 +03:00

This file is the shortest bootstrap for a completely fresh ChatGPT development chat.

## Source of truth

- Repository: `Numillyash/planets-intel`
- Active development branch: `feature/operational-ui`
- Do not reconstruct implementation state from old chat history.
- First read:
  1. `docs/architecture/NEW_CHAT_START.md`
  2. `docs/architecture/PROJECT_STATE.md`
  3. `docs/architecture/CURRENT_HANDOFF.md`
- Then inspect the actual branch HEAD and server checkout before changing code.

The old `feature/post-combat-ammo-runtime` branch is already an ancestor of `feature/operational-ui`; do not resume development from it.

`main` is intentionally not the current development source of truth and is diverged from the operational branch. Do not merge/reset it merely to start a new chat.

## Durable checkpoint

A GitHub checkpoint branch exists specifically for chat/session recovery:

```text
checkpoint/2026-08-15-intelboard-handoff
```

It should point at the final handoff commit after this file is created. Continue normal work on `feature/operational-ui`; use the checkpoint only as a recovery anchor.

## Server

```text
checkout: /opt/planets-intel
health:   http://127.0.0.1:18080/api/health
```

The `backend` Docker image builds and embeds the React/Vite frontend, so `docker compose build backend` validates both backend and frontend.

Because the server has an old Git version, prefer:

```bash
git symbolic-ref --quiet --short HEAD
```

instead of relying on `git branch --show-current`.

## First commands in the new chat

Run this before any code change:

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

If the tree is clean and the server is behind:

```bash
git pull --ff-only origin feature/operational-ui

docker compose build backend >/tmp/pi-build.log 2>&1 \
  && echo 'BUILD: OK' \
  || { echo 'BUILD: FAILED'; tail -80 /tmp/pi-build.log; exit 1; }

docker compose up -d --force-recreate backend >/dev/null
sleep 2
curl -fsS http://127.0.0.1:18080/api/health && echo
```

## Last runtime fact from the old chat

The last explicit artwork diagnostic shown on the server was:

```text
Hull #69: RESULT OK
CACHE: /app/private_assets/hulls/69.png

Hull #94: RESULT ERROR
all mobile/app/play hull and hulls3d candidates timed out
```

The source list printed by that deployed runtime still contained only `mobile.planets.nu`, `app.planets.nu` and `play.planets.nu`. Therefore that runtime was older than the newest resilient artwork-fetch changes already present in GitHub.

The current GitHub operational branch contains a newer artwork downloader that adds direct/proxy fallback behavior, `planets.nu` candidates, concurrency limiting and larger timeout/read budgets. Deploy the actual branch HEAD first, then re-test hull #94 before making more artwork changes.

Useful re-test:

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

## Last validated IntelBoard semantics

Hard invariants that must survive future changes:

```text
known zero != unknown
fact != inference != simulation
combat-time evidence != current factual state
```

Confirmed examples in game `682909`:

- own SSD #43: factual `ammo=45` -> UI shows 45 fighters;
- own SSD #62: factual `ammo=25` -> UI shows 25 fighters;
- own SSD #22: factual `ammo=0` -> known zero;
- enemy Rush #63: fighter bays are known, current fighters remain `UNKNOWN` unless factual evidence exists;
- VCR equipment is immutable combat-start evidence and must not overwrite current ship state.

The game-list and `/games/{id}` routes have canonical DB fallbacks so an upstream Planets.nu outage must not make already-known games disappear from IntelBoard.

For full Military-delta, movement, VCR, warp-well, order-draft and offline-read details, read `CURRENT_HANDOFF.md` and `PROJECT_STATE.md`.

## Immediate priorities after deploy verification

1. Re-test hull #94 against the newest artwork downloader.
2. Validate the newest VCR fighter-evidence section in `Scoreboard -> Military Δ intelligence` for `tusilat`, T11 -> T12.
3. Keep combat-time fighter evidence separate from current carrier loadout and only attribute Military delta when evidence is time-compatible.
4. Then continue Battle Planner / movement fuel / Tow work according to `PROJECT_STATE.md`.
